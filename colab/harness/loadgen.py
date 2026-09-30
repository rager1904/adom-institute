#!/usr/bin/env python3
"""
Async HTTP load driver for ADOM Institute.

Design decisions worth knowing about:

* **Ramp, not a single number.** Throughput measured at concurrency 1 tells you
  almost nothing. The driver steps through a concurrency ladder (1, 5, 10, 20,
  ...) and reports RPS plus latency percentiles per step, so you can see the
  knee -- the point where adding concurrency stops adding throughput and only
  adds queueing delay.

* **Closed loop, not a fixed rate.** Each virtual user issues its next request
  as soon as the previous one returns. This is the standard model for measuring
  capacity. It cannot tell you what happens at a fixed 500 rps arrival rate,
  which is what a load balancer would do to you in production; if you need
  that, use a rate-based mode.

* **Latency is measured around the whole request**, connection reuse included.
  We read the response body, because a server that streams a 4 MB list and
  blocks halfway through is not "fast".

* **The driver runs in the same process space as the server.** In Colab that
  means the load generator competes with Postgres, Redis, Celery and the ASGI
  server for the same 2 vCPUs, so absolute numbers are pessimistic. The shape
  of the curve and the relative cost of each endpoint are still valid, and the
  ratios are what you are after. See the notebook's caveats cell.

Percentiles are exact (full sort of the sample), not estimated from a
histogram, because the sample sizes here are small enough that the error of
bucket interpolation would swamp the differences we care about.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

try:
    import aiohttp
except ImportError:  # pragma: no cover
    print(
        "aiohttp is required: pip install aiohttp",
        file=sys.stderr,
    )
    raise

_HERE = Path(__file__).resolve().parent
# `harness` lives in colab/; the Django project (`adom`) lives in the repo root
# one level above. Appending rather than inserting keeps stdlib precedence.
for _p in (_HERE.parent.parent, _HERE.parent):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

from harness.scenarios import Scenario, describe_catalogue, get_scenarios  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def substitute(template: str, values: dict) -> str:
    """
    Replace ``{name}`` tokens by literal substitution.

    str.format() is unusable here: request bodies are JSON, so every key is
    surrounded by braces that str.format would try to interpret as a field name
    ("student" in ``{"student": 1}`` is read as a replacement key and raises
    KeyError). Literal replacement has no such surprises.
    """
    out = template
    for key, value in values.items():
        token = "{" + key + "}"
        if token in out:
            out = out.replace(token, str(value))
    return out


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #

def percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolated percentile over an already-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


@dataclass
class Result:
    name: str
    role: str
    category: str
    count: int = 0
    #: Requests that did not return 2xx/3xx. 429 is excluded: the throttle
    #: working as designed is not a failure.
    errors: int = 0
    #: 5xx. A server bug -- these invalidate the measurements.
    server_errors: int = 0
    #: 4xx other than 429: bad token, wrong role, malformed request.
    client_errors: int = 0
    #: No HTTP response at all: timeout, reset, refused.
    transport_errors: int = 0
    #: 429 from the DRF throttles.
    throttled: int = 0
    status_counts: dict[int, int] = field(default_factory=dict)
    latencies_ms: list[float] = field(default_factory=list)
    bytes_read: int = 0
    error_samples: list[str] = field(default_factory=list)

    def record(self, latency_ms: float, status: int | None, size: int, error: str | None):
        self.count += 1
        self.latencies_ms.append(latency_ms)
        self.bytes_read += size
        key = status if status is not None else 0
        self.status_counts[key] = self.status_counts.get(key, 0) + 1
        if error and error not in self.error_samples and len(self.error_samples) < 3:
            self.error_samples.append(error[:200])
        # A 5xx or a missing response means the stack is broken. A 4xx is
        # usually a role/token problem. Keeping these apart is the whole point:
        # a single flag for "any non-2xx" made a run whose only failures were
        # 404s report "5xx" and exit non-zero.
        if status is None:
            self.transport_errors += 1
            self.errors += 1
        elif status >= 500:
            self.server_errors += 1
            self.errors += 1
        elif status == 429:
            self.throttled += 1
        elif status >= 400:
            self.client_errors += 1
            self.errors += 1

    @property
    def broken(self) -> int:
        """5xx plus transport failures: the outcomes that mean the server broke."""
        return self.server_errors + self.transport_errors

    @property
    def error_rate(self) -> float:
        return (self.errors / self.count * 100.0) if self.count else 0.0

    def stats(self) -> dict:
        s = sorted(self.latencies_ms)
        return {
            "name": self.name,
            "role": self.role or "anon",
            "category": self.category,
            "count": self.count,
            "errors": self.errors,
            "server_errors": self.server_errors,
            "client_errors": self.client_errors,
            "transport_errors": self.transport_errors,
            "throttled": self.throttled,
            "broken": self.broken,
            "error_rate_pct": round(self.error_rate, 2),
            "status_counts": {str(k): v for k, v in sorted(self.status_counts.items())},
            "min_ms": round(percentile(s, 0), 2),
            "mean_ms": round(statistics.fmean(s), 2) if s else 0.0,
            "p50_ms": round(percentile(s, 50), 2),
            "p75_ms": round(percentile(s, 75), 2),
            "p90_ms": round(percentile(s, 90), 2),
            "p95_ms": round(percentile(s, 95), 2),
            "p99_ms": round(percentile(s, 99), 2),
            "max_ms": round(percentile(s, 100), 2),
            "kb_per_s": round(self.bytes_read / 1024.0, 1),
            "error_samples": self.error_samples,
        }


# --------------------------------------------------------------------------- #
# Request context
# --------------------------------------------------------------------------- #

class Context:
    """
    Per-virtual-user request context. Each VU gets its own so that
    token rotation, pagination position and write-pair consumption do not race.
    """

    def __init__(self, manifest: dict, rng: random.Random, page_span: int = 0,
                 page_limits: dict[str, int] | None = None, page_size: int = 20):
        self.rng = rng
        self.page_span = page_span
        self.page_size = page_size
        #: Shared across virtual users: the page count belongs to the endpoint
        #: and the dataset, not to the VU, so it is learned once per run.
        self.page_limits = {} if page_limits is None else page_limits
        samples = manifest.get("samples", {})
        self.student_ids: list[int] = samples.get("student_ids") or [1]
        self.write_pairs: list[dict] = samples.get("write_pairs") or [
            {"student_id": self.student_ids[0], "date": date.today().isoformat()}
        ]
        self.class_rosters: dict[int, list[int]] = {
            int(k): v for k, v in (samples.get("class_rosters") or {}).items() if v
        }
        self.class_ids: list[int] = [c for c, v in sorted(self.class_rosters.items())] or [1]
        self.attendance_dates: list[str] = samples.get("attendance_dates") or [
            date.today().isoformat()
        ]

        tokens = manifest.get("tokens", {})
        self.tokens: dict[str, list[str]] = {
            k: v for k, v in tokens.items() if not k.startswith("_") and v
        }
        self._pair_cursor = 0
        self._search_words = ["m", "a", "ka", "sim", "test", "STU10", "e"]

    # -- token selection ---------------------------------------------------- #

    def token_for(self, role: str | None) -> str | None:
        if role is None:
            return None
        pool = self.tokens.get(role)
        if not pool:
            return None
        return self.rng.choice(pool)

    # -- placeholder filling ------------------------------------------------ #

    def next_write_pair(self) -> dict:
        pair = self.write_pairs[self._pair_cursor % len(self.write_pairs)]
        self._pair_cursor += 1
        return pair

    def attendance_block(self, class_id: int, limit: int = 25) -> str:
        roster = self.class_rosters.get(class_id, [])
        if not roster:
            roster = self.student_ids[:limit]
        chosen = roster[:limit]
        rows = [
            {"student_id": sid, "status": "present", "remarks": ""} for sid in chosen
        ]
        return json.dumps(rows)

    def _page_for(self, key: str) -> int:
        """The highest ``?page=`` worth sending for this scenario.

        Learned from the ``count`` field of the first paginated response rather
        than guessed from a fixed span. Picking a page uniformly from a fixed
        1..40 span guaranteed 404 ``{"detail": "Invalid page."}`` for every
        endpoint with fewer than 40 pages, which the driver then counted as an
        error -- a failure caused entirely by the driver, not the app. Until a
        count is known, send page 1, which is always valid.
        """
        if self.page_span > 0:
            return self.rng.randint(1, self.page_span)
        known = self.page_limits.get(key)
        if not known:
            return 1
        return self.rng.randint(1, known)

    def observe(self, key: str, status: int | None, payload: bytes) -> None:
        """Learn, or correct, the page count for a scenario from one response.

        Only runs while the count for this scenario is still unknown, so the
        JSON parse cost is paid once per scenario per run rather than once per
        request. Skipped entirely when ``--page-span`` pins the range.
        """
        if self.page_span > 0 or not payload:
            return
        # Cheap, and always evaluated. A stale count makes every subsequent
        # request to that endpoint return 404, so shrinking is what stops the
        # driver re-deriving an out-of-range page forever.
        if status == 404 and b"Invalid page" in payload:
            # The count we learned was stale -- rows were inserted, or the
            # endpoint's role scope changed.
            cur = self.page_limits.get(key)
            if cur and cur > 1:
                self.page_limits[key] = cur - 1
            return
        # The parse below costs CPU on the same 2 vCPUs as the server, so it
        # only runs while the count for this scenario is still unknown -- once
        # per scenario per run, not once per request.
        if key in self.page_limits or status != 200:
            return
        try:
            doc = json.loads(payload)
        except Exception:
            return
        if not isinstance(doc, dict):
            return
        count = doc.get("count")
        if not isinstance(count, int) or "results" not in doc:
            return
        self.page_limits[key] = max(1, -(-count // max(1, self.page_size)))

    def fill(self, scenario: Scenario) -> tuple[str, str | None, dict | None]:
        """Return (path, json_body_str, headers) with placeholders substituted."""
        pair = self.next_write_pair()
        # Pick the class ONCE and derive the roster block from that same class.
        # Substituting them independently would declare a class_obj that does not
        # contain the students in the payload, and the view's per-row access
        # check would reject the whole request.
        class_id = self.rng.choice(self.class_ids)
        values = {
            "page": self._page_for(scenario.key),
            "student_id": self.rng.choice(self.student_ids),
            "class_id": class_id,
            "attendance_block": self.attendance_block(class_id),
            "date": self.rng.choice(self.attendance_dates),
            "date_from": (date.today() - timedelta(days=14)).isoformat(),
            "search": self.rng.choice(self._search_words),
            "student_pk": pair["student_id"],
            "write_date": pair["date"],
        }
        # Explicit substitution, NOT str.format: JSON bodies and query strings
        # are full of literal braces, and str.format would either eat them or
        # raise KeyError on `"key":` pairs.
        path = substitute(scenario.path, values)
        body = substitute(scenario.body, values) if scenario.body else None
        return path, body, None


# --------------------------------------------------------------------------- #
# The driver
# --------------------------------------------------------------------------- #

@dataclass
class RunConfig:
    base_url: str = DEFAULT_BASE_URL
    host_header: str | None = None
    duration: float = 10.0
    warmup: float = 3.0
    timeout: float = 60.0
    seed: int = 7
    bulk_limit: int = 25
    #: 0 = learn the real page count from each response. A positive value pins
    #: the range and restores the old guess-at-a-page behaviour.
    page_span: int = 0
    page_size: int = 20
    verbose: bool = True


class LoadDriver:
    def __init__(self, config: RunConfig, manifest: dict, scenarios: list[Scenario]):
        self.cfg = config
        self.scenarios = scenarios
        self.weights = [s.weight for s in scenarios]
        self.manifest = manifest
        self.results: dict[str, Result] = {}
        self.timeline: list[tuple[float, float]] = []  # (elapsed_s, instantaneous rps)
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._started = 0.0
        #: Learned page counts, keyed by Scenario.key, shared by every VU.
        self.page_limits: dict[str, int] = {}

    def _context(self, seed: int) -> Context:
        return Context(
            self.manifest,
            random.Random(seed),
            page_span=self.cfg.page_span,
            page_limits=self.page_limits,
            page_size=self.cfg.page_size,
        )

    def _result_for(self, scenario: Scenario) -> Result:
        key = scenario.key
        if key not in self.results:
            self.results[key] = Result(scenario.name, scenario.role or "anon", scenario.category)
        return self.results[key]

    async def _sample_sampler(self):
        """Record per-second throughput so the report can show saturation."""
        last_count = 0
        while not self._stop.is_set():
            await asyncio.sleep(1.0)
            total = sum(r.count for r in self.results.values())
            now = time.perf_counter() - self._started
            self.timeline.append((round(now, 2), total - last_count))
            last_count = total
            if self.cfg.verbose:
                self._print_live(total, now)

    def _print_live(self, total: int, elapsed: float):
        lat = [x for r in self.results.values() for x in r.latencies_ms]
        lat.sort()
        rps = total / elapsed if elapsed else 0
        errs = sum(r.errors for r in self.results.values())
        print(
            f"    t={elapsed:5.1f}s  reqs={total:6d}  rps={rps:7.1f}  "
            f"p50={percentile(lat, 50):8.1f}ms  p95={percentile(lat, 95):9.1f}ms  "
            f"err={errs}",
            flush=True,
        )

    async def _worker(self, session: aiohttp.ClientSession, ctx: Context, count_warmup: bool):
        rng = ctx.rng
        while not self._stop.is_set():
            scenario = rng.choices(self.scenarios, weights=self.weights, k=1)[0]
            path, body, _ = ctx.fill(scenario)

            headers = {"Accept": "*/*"}
            # When DEBUG=False Django validates the Host header against
            # ALLOWED_HOSTS, which must not contain 127.0.0.1. The driver
            # therefore connects to loopback but presents the public hostname.
            if self.cfg.host_header:
                headers["Host"] = self.cfg.host_header
            token = ctx.token_for(scenario.role)
            if token:
                headers["Authorization"] = f"Token {token}"
            if body is not None:
                headers["Content-Type"] = "application/json"

            url = self.cfg.base_url.rstrip("/") + path
            t0 = time.perf_counter()
            status: int | None = None
            size = 0
            error: str | None = None
            try:
                async with session.request(
                    scenario.method, url, data=body, headers=headers,
                    allow_redirects=False, timeout=aiohttp.ClientTimeout(total=self.cfg.timeout),
                ) as resp:
                    status = resp.status
                    payload = await resp.read()
                    size = len(payload)
                    if scenario.uses_page:
                        # Learns the real page count once per scenario, so the
                        # driver stops inventing out-of-range ?page= values.
                        ctx.observe(scenario.key, status, payload)
                    if status >= 400 and status != 429:
                        error = f"HTTP {status}: {payload[:160].decode('utf-8', 'replace')}"
            except asyncio.TimeoutError:
                error = f"timeout after {self.cfg.timeout}s"
            except Exception as exc:  # noqa: BLE001 - we want the failure recorded
                error = f"{type(exc).__name__}: {exc}"

            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # Warmup traffic is excluded from the statistics, but the requests
            # are still sent so caches and the connection pool are warm.
            if not count_warmup:
                res = self._result_for(scenario)
                res.record(elapsed_ms, status, size, error)

    async def run_step(self, concurrency: int) -> dict:
        """Run one concurrency level for cfg.duration seconds."""
        for key in list(self.results):
            del self.results[key]
        self.timeline = []
        self._stop = asyncio.Event()

        connector = aiohttp.TCPConnector(
            limit=concurrency, limit_per_host=concurrency, ttl_dns_cache=300, force_close=False
        )
        timeout = aiohttp.ClientTimeout(total=self.cfg.timeout)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Warmup
            if self.cfg.warmup > 0 and self.cfg.verbose:
                print(f"    warmup {self.cfg.warmup:.0f}s ...", flush=True)
            self._stop.clear()
            sampler = asyncio.create_task(self._sample_sampler())
            warm_ctxs = [self._context(self.cfg.seed + i) for i in range(concurrency)]
            warm_tasks = [
                asyncio.create_task(self._worker(session, c, True)) for c in warm_ctxs
            ]
            await asyncio.sleep(self.cfg.warmup)
            self._stop.set()
            for t in warm_tasks:
                t.cancel()
            await asyncio.gather(*warm_tasks, return_exceptions=True)
            sampler.cancel()
            await asyncio.gather(sampler, return_exceptions=True)

            # Measured run
            if self.cfg.verbose:
                print(
                    f"    measuring {self.cfg.duration:.0f}s at concurrency {concurrency} ...",
                    flush=True,
                )
            self._stop.clear()
            self._started = time.perf_counter()
            sampler = asyncio.create_task(self._sample_sampler())
            ctxs = [self._context(self.cfg.seed + 1000 + i) for i in range(concurrency)]
            tasks = [asyncio.create_task(self._worker(session, c, False)) for c in ctxs]
            await asyncio.sleep(self.cfg.duration)
            self._stop.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            sampler.cancel()
            await asyncio.gather(sampler, return_exceptions=True)
            wall = time.perf_counter() - self._started

        per_scenario = [r.stats() for r in self.results.values()]
        total = sum(r.count for r in self.results.values())
        errors = sum(r.errors for r in self.results.values())
        server_errors = sum(r.server_errors for r in self.results.values())
        client_errors = sum(r.client_errors for r in self.results.values())
        transport_errors = sum(r.transport_errors for r in self.results.values())
        throttled = sum(r.throttled for r in self.results.values())
        all_lat = sorted(x for r in self.results.values() for x in r.latencies_ms)
        return {
            "concurrency": concurrency,
            "wall_seconds": round(wall, 2),
            "requests": total,
            "errors": errors,
            "server_errors": server_errors,
            "client_errors": client_errors,
            "transport_errors": transport_errors,
            "throttled": throttled,
            "broken": server_errors + transport_errors,
            "error_rate_pct": round(errors / total * 100.0, 2) if total else 0.0,
            "rps": round(total / wall, 2) if wall else 0.0,
            "p50_ms": round(percentile(all_lat, 50), 2),
            "p90_ms": round(percentile(all_lat, 90), 2),
            "p95_ms": round(percentile(all_lat, 95), 2),
            "p99_ms": round(percentile(all_lat, 99), 2),
            "max_ms": round(percentile(all_lat, 100), 2),
            "timeline": self.timeline,
            "scenarios": sorted(per_scenario, key=lambda s: -s["count"]),
        }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def check_scenario_routes(scenarios: list[Scenario]) -> tuple[list[str], bool]:
    """Find scenarios whose path will not actually measure an endpoint.

    Guards the specific failure that made a previous run meaningless: a
    scenario pointing at a ``DefaultRouter`` root. ``adom/urls.py`` mounts each
    app's router at ``/api/v1/<app>/``, so ``/api/v1/students/`` resolves to
    ``APIRootView``, which answers **200 with the route list** and never
    touches a table. Nine of thirty-two scenarios were aimed that way -- 48% of
    the total weight -- and every one of them was counted as a success. Worse,
    ``APIRootView`` only defines ``get``, so the two POST write scenarios
    aimed at a root returned **405** and the benchmark never performed a single
    write.

    Returns (problems, checked). ``checked`` is False when Django cannot be
    imported, in which case the caller skips the check rather than failing --
    the driver has to stay runnable outside the project directory.
    """
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adom.settings")
        import django
        from django.apps import apps
        from django.urls import Resolver404, resolve
        if not apps.ready:
            django.setup()
        import adom.urls  # noqa: F401  (forces the URLconf to import)
    except Exception as exc:  # noqa: BLE001 - a missing Django is not fatal here
        print(f"  routes: check skipped ({type(exc).__name__}: {exc})")
        return [], False

    problems: list[str] = []
    for s in scenarios:
        path = re.sub(r"\{[^}]+\}", "1", s.path).split("?")[0]
        try:
            match = resolve(path)
        except Resolver404:
            problems.append(f"{s.name:<30} {path}  -> no such route (404)")
            continue
        func = match.func
        cls = getattr(func, "cls", None) or getattr(func, "view_class", None)
        if isinstance(cls, type) and cls.__name__ == "APIRootView":
            problems.append(
                f"{s.name:<30} {path}  -> DRF router root: returns the route "
                f"list with no rows, and POST would return 405"
            )
    return problems, True


def describe_failures(steps: list[dict]) -> tuple[bool, bool]:
    """Name every endpoint that did not return 2xx, with a sample response.

    5xx, transport failures and 4xx are counted separately, because they mean
    different things:

    * **5xx / no response** -- the server is broken under load. The latency and
      throughput figures above are meaningless.
    * **4xx** -- usually a role, token or malformed-request problem. Worth
      reporting, but it does not invalidate the measurements.

    This used to raise one ``server_error`` flag for *any* non-2xx, so a run
    whose only failures were 404s printed "at least one request returned 5xx or
    failed at the transport level" and exited non-zero. That is worse than
    reporting nothing: it points at a server bug that is not there. Only
    ``server_errors + transport_errors`` decides the exit code now.

    Returns (saw_broken, saw_any_failure).
    """
    broken = False
    any_bad = False
    totals = {"5xx": 0, "4xx": 0, "transport": 0, "throttled": 0}
    print()
    print("=" * 100)
    print("RESPONSE FAILURES")
    print("=" * 100)
    for step in steps:
        rows = []
        for s in step["scenarios"]:
            bad = {c: n for c, n in s["status_counts"].items()
                   if not (c == "0" or 200 <= int(c) < 400)}
            if not bad and not s["errors"]:
                continue
            rows.append(s)
            any_bad = True
            totals["5xx"] += s["server_errors"]
            totals["4xx"] += s["client_errors"]
            totals["transport"] += s["transport_errors"]
            totals["throttled"] += s["throttled"]
            if s["broken"]:
                broken = True
        if not rows:
            continue
        print(f"\n  concurrency {step['concurrency']}  "
              f"({len(rows)} scenario(s) with a non-2xx response)")
        for s in rows:
            print(f"    {s['name']:<30} role={s['role']:<12} "
                  f"count={s['count']:<6} errors={s['errors']:<5} "
                  f"5xx={s['server_errors']:<4} 4xx={s['client_errors']:<4} "
                  f"transport={s['transport_errors']:<4} "
                  f"statuses={s['status_counts']}")
            for sample in s.get("error_samples", [])[:2]:
                print(f"        {sample}")

    print()
    print(f"  totals: {totals['5xx']} 5xx, {totals['4xx']} 4xx, "
          f"{totals['transport']} transport failure(s), "
          f"{totals['throttled']} throttled (429)")
    if not any_bad:
        print("  every measured request returned 2xx or 3xx.")
    elif broken:
        print(f"  !! {totals['5xx']} request(s) returned 5xx and "
              f"{totals['transport']} failed at the transport level.")
        print("     The server is failing under this load; the latency and")
        print("     throughput figures above are not meaningful.")
        print("     Read the server log for the traceback -- that is the only")
        print("     way to tell which component gave up.")
    else:
        print(f"  no 5xx and no transport failures. The {totals['4xx']} 4xx above are")
        print("  request problems (role, token, bad parameter), not a broken")
        print("  endpoint -- the latency and throughput figures are still valid.")
        if totals["throttled"]:
            print(f"  {totals['throttled']} request(s) were throttled (429), which is")
            print("  DRF's rate limiter working as configured, not a failure.")
    return broken, any_bad


def print_step(step: dict) -> None:
    print()
    print("  " + "-" * 96)
    print(
        f"  concurrency {step['concurrency']:>3}   "
        f"{step['requests']:>6} reqs in {step['wall_seconds']:.1f}s   "
        f"{step['rps']:>7.1f} rps   "
        f"p50={step['p50_ms']:.1f} p90={step['p90_ms']:.1f} "
        f"p95={step['p95_ms']:.1f} p99={step['p99_ms']:.1f} ms   "
        f"errors={step['errors']} ({step['error_rate_pct']}%)  "
        f"[5xx={step['server_errors']} 4xx={step['client_errors']} "
        f"transport={step['transport_errors']} 429={step['throttled']}]"
    )
    print("  " + "-" * 96)
    header = (
        f"  {'scenario':<32}{'role':<14}{'n':>6}{'err':>5}"
        f"{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}  statuses"
    )
    print(header)
    for s in step["scenarios"]:
        if not s["count"]:
            continue
        statuses = ",".join(f"{k}:{v}" for k, v in list(s["status_counts"].items())[:4])
        print(
            f"  {s['name']:<32}{s['role']:<14}{s['count']:>6}{s['errors']:>5}"
            f"{s['p50_ms']:>9.1f}{s['p95_ms']:>9.1f}{s['p99_ms']:>9.1f}{s['max_ms']:>9.1f}  {statuses}"
        )
        for e in s["error_samples"]:
            print(f"      ! {e}")


def print_summary(steps: list[dict], dataset: dict) -> None:
    print()
    print("=" * 100)
    print("SCALING SUMMARY")
    print("=" * 100)
    print(
        f"  {'conc':>5}{'rps':>10}{'p50':>10}{'p95':>10}{'p99':>10}"
        f"{'err%':>8}{'5xx':>6}{'4xx':>6}{'tran':>6}{'rps/conc':>11}"
    )
    best = 0.0
    for s in steps:
        per = s["rps"] / s["concurrency"] if s["concurrency"] else 0.0
        best = max(best, s["rps"])
        print(
            f"  {s['concurrency']:>5}{s['rps']:>10.1f}{s['p50_ms']:>10.1f}"
            f"{s['p95_ms']:>10.1f}{s['p99_ms']:>10.1f}{s['error_rate_pct']:>8.2f}"
            f"{s['server_errors']:>6}{s['client_errors']:>6}{s['transport_errors']:>6}"
            f"{per:>11.2f}"
        )

    # The knee: first level where throughput gain per added connection drops
    # below a third, or p95 doubles versus the previous step.
    print()
    knee = None
    for prev, cur in zip(steps, steps[1:]):
        if prev["rps"] <= 0:
            continue
        gain = (cur["rps"] - prev["rps"]) / max(prev["rps"], 1e-9)
        if gain < 0.33 or cur["p95_ms"] > max(prev["p95_ms"] * 2, prev["p95_ms"] + 200):
            knee = cur["concurrency"]
            print(
                f"  knee at concurrency {knee}: throughput gained only "
                f"{gain * 100:.0f}% while p95 went {prev['p95_ms']:.0f} -> {cur['p95_ms']:.0f} ms"
            )
            break
    if knee is None:
        print("  no knee detected within the tested range -- the stack absorbed every level")

    print()
    print(f"  peak throughput : {best:.1f} rps")
    tier = dataset.get("tier", "?")
    ram = dataset.get("ram_gb", "?")
    cpu = dataset.get("cpu", "?")
    print(f"  dataset         : tier={tier}, {cpu} vCPU / {ram} GB runtime")
    counts = dataset.get("counts", {})
    if counts:
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
        print(
            "  largest tables  : "
            + ", ".join(f"{k}={v:,}" for k, v in top if v)
        )
    print()
    print(
        "  NOTE: the load generator shares the same CPUs as Postgres, Redis, Celery"
    )
    print(
        "  and the app server, so absolute rps understates a dedicated-host setup."
    )
    print("  Ratios between endpoints and the shape of the curve are still meaningful.")


# --------------------------------------------------------------------------- #

def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_ladder(spec: str) -> list[int]:
    if not spec or spec.strip() == "":
        return [1, 5, 10, 20, 40]
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


async def amain(args) -> int:
    manifest = load_manifest(Path(args.manifest))
    scenarios = get_scenarios(
        include=args.only.split(",") if args.only else None,
        exclude=args.exclude.split(",") if args.exclude else None,
        categories=args.categories.split(",") if args.categories else None,
    )
    if not scenarios:
        print("no scenarios matched the filters", file=sys.stderr)
        return 2

    cfg = RunConfig(
        base_url=args.base_url,
        host_header=args.host_header or None,
        duration=args.duration,
        warmup=args.warmup,
        timeout=args.timeout,
        seed=args.seed,
        page_span=args.page_span,
        page_size=args.page_size,
    )
    driver = LoadDriver(cfg, manifest, scenarios)
    ladder = parse_ladder(args.concurrency)

    print("=" * 100)
    print("ADOM Institute load driver")
    print("=" * 100)
    print(f"  target   : {cfg.base_url}")
    print(f"  Host hdr : {cfg.host_header or '(none)'}")
    print(f"  scenarios: {len(scenarios)}")
    print(f"  duration : {cfg.duration}s per level, {cfg.warmup}s warmup")
    print(f"  ladder   : {ladder}")
    print(f"  pages    : {'learned from responses' if cfg.page_span == 0 else f'random 1..{cfg.page_span}'}")

    # Refuse to measure anything that would report a healthy 200 while reading
    # no data. A silent no-op is the one failure a load test cannot detect on
    # its own, so it is worth failing loudly before spending 90 seconds on it.
    if args.check_routes:
        problems, checked = check_scenario_routes(scenarios)
        if checked and problems:
            print()
            print("!" * 100)
            print("REFUSING TO RUN: these scenario paths do not resolve to a real endpoint")
            print("!" * 100)
            for p in problems:
                print("  !!", p)
            print()
            print("  Fix the paths in colab/harness/scenarios.py, narrow the run with")
            print("  --only/--exclude, or pass --no-check-routes to measure anyway.")
            return 2
        if checked:
            print(f"  routes   : all {len(scenarios)} scenario paths resolve to real endpoints")
    print()
    for s in scenarios:
        who = s.role or "anon"
        print(f"    {s.name:<32} {s.method:<5} {who:<14} w={s.weight:<3} {s.path}")

    steps = []
    for level in ladder:
        step = await driver.run_step(level)
        steps.append(step)
        print_step(step)

    print_summary(steps, manifest.get("scale", {}))
    broken, any_bad = describe_failures(steps)

    out = Path(args.out) if args.out else Path.cwd() / "loadtest_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "target": cfg.base_url,
                "host_header": cfg.host_header,
                "duration": cfg.duration,
                "scale": manifest.get("scale", {}),
                # `broken` is the verdict the notebook keys off: true only for
                # 5xx or a missing response.
                "broken": broken,
                "any_bad_status": any_bad,
                "steps": steps,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n  raw results: {out}")
    if broken:
        # The notebook turns a non-zero exit into "load test failed"; give it
        # something to say beyond that.
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default=".colab_loadtest/manifest.json")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument(
        "--host-header", default="",
        help="Value for the Host header. Required when the app runs with DEBUG=False, "
             "because settings.py refuses ALLOWED_HOSTS=localhost in that mode.",
    )
    p.add_argument("--duration", type=float, default=10.0, help="Seconds per level")
    p.add_argument("--warmup", type=float, default=3.0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument(
        "--page-span", type=int, default=0,
        help="Pick ?page= uniformly from 1..N. 0 (default) learns the real page "
             "count from each response, which is what stops the driver sending "
             "?page=40 to an endpoint with 3 pages and recording the resulting "
             "404 as an application failure.",
    )
    p.add_argument(
        "--page-size", type=int, default=20,
        help="Page size used to convert a response's `count` into a page total. "
             "Must match the app's REST_FRAMEWORK PAGE_SIZE (default 20).",
    )
    p.add_argument(
        "--check-routes", dest="check_routes", action="store_true", default=True,
        help="Verify every scenario path resolves to a real endpoint before "
             "measuring (default). Catches scenarios aimed at a DRF router root, "
             "which return 200 while reading no data.",
    )
    p.add_argument(
        "--no-check-routes", dest="check_routes", action="store_false",
        help="Skip the pre-flight route check.",
    )
    p.add_argument("--concurrency", default="1,5,10,20,40",
                   help="Ladder. Supports ranges, e.g. '1,4,8-32'")
    p.add_argument("--only", default="", help="Comma-separated scenario names to include")
    p.add_argument("--exclude", default="", help="Comma-separated scenario names to skip")
    p.add_argument("--categories", default="",
                   help="Comma-separated categories: read,scoped,write,page")
    p.add_argument("--out", default="")
    p.add_argument("--list", action="store_true", help="Print the scenario catalogue and exit")
    args = p.parse_args()

    if args.list:
        print(describe_catalogue())
        return 0

    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
