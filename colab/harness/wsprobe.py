#!/usr/bin/env python3
"""
WebSocket probe for the Django Channels notification/chat endpoints.

Why this is separate from loadgen: Channels authenticates with a *session
cookie*, not a DRF token (``AuthMiddlewareStack`` in adom/asgi.py:24), so the
probe has to perform a real form login through ``/accounts/login/`` first,
carrying the CSRF token. That is a one-time cost per virtual user.

It measures two things that HTTP benchmarks cannot:

* handshake latency and success rate under concurrency, and
* fan-out: how long a notification takes to travel from the server to connected
  clients, which is the operation the school actually depends on when a teacher
  marks attendance and 40 parents expect a push.

A side effect is that ChatConsumer writes Message rows (consumers.py:142), so
the chat probe leaves data behind. That is intended -- it makes the write
volume realistic.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import aiohttp
    import websockets
except ImportError:  # pragma: no cover
    print("requires: pip install aiohttp websockets", file=sys.stderr)
    raise

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass
class WsResult:
    name: str
    clients: int = 0
    connected: int = 0
    failed: int = 0
    connect_ms: list[float] = field(default_factory=list)
    messages_received: int = 0
    errors: list[str] = field(default_factory=list)
    #: Broadcast delivery latency, filled in during the fan-out phase.
    fanout_ms: list[float] = field(default_factory=list)

    @property
    def connect_success_pct(self) -> float:
        return (self.connected / self.clients * 100.0) if self.clients else 0.0

    def summary(self) -> dict:
        def pct(values, p):
            if not values:
                return 0.0
            s = sorted(values)
            k = (len(s) - 1) * (p / 100.0)
            lo, hi = int(k), min(int(k) + 1, len(s) - 1)
            return s[lo] + (s[hi] - s[lo]) * (k - lo)

        return {
            "name": self.name,
            "clients": self.clients,
            "connected": self.connected,
            "failed": self.failed,
            "connect_success_pct": round(self.connect_success_pct, 2),
            "connect_p50_ms": round(pct(self.connect_ms, 50), 2),
            "connect_p95_ms": round(pct(self.connect_ms, 95), 2),
            "connect_max_ms": round(pct(self.connect_ms, 100), 2),
            "messages_received": self.messages_received,
            "fanout_p50_ms": round(pct(self.fanout_ms, 50), 2),
            "fanout_p95_ms": round(pct(self.fanout_ms, 95), 2),
            "errors": self.errors[:5],
        }


CSRF_RE = re.compile(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']')


async def login(
    session: aiohttp.ClientSession, base_url: str, email: str, password: str
) -> tuple[str | None, str | None]:
    """
    Log in through the HTML form and return (sessionid_cookie, detail).

    Returns (None, reason) on failure. The caller should treat that as "this
    virtual user could not authenticate" rather than crashing the probe.
    """
    login_url = f"{base_url.rstrip('/')}/accounts/login/"
    try:
        async with session.get(login_url) as resp:
            html = await resp.text()
            cookie = resp.cookies.get("csrftoken")
            match = CSRF_RE.search(html)
            token = match.group(1) if match else cookie
            if not token:
                return None, "no CSRF token in login page"
            payload = {
                "csrfmiddlewaretoken": token,
                "email": email,
                "password": password,
            }
            headers = {"Referer": login_url}
            if cookie:
                headers["X-CSRFToken"] = cookie
            async with session.post(
                login_url, data=payload, headers=headers, allow_redirects=False
            ) as post:
                if post.status in (301, 302, 303):
                    sessionid = session.cookie_jar.filter_cookies(base_url)
                    sid = None
                    for c in sessionid:
                        if c.key == "sessionid":
                            sid = c.value
                    if sid:
                        return sid, None
                    return None, "redirected but no sessionid cookie"
                return None, f"login returned HTTP {post.status}"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


class WsProbe:
    def __init__(self, cfg, manifest: dict):
        self.cfg = cfg
        self.manifest = manifest
        self.sessions: list[aiohttp.ClientSession] = []

    async def _session(self) -> aiohttp.ClientSession:
        if not self.sessions:
            s = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                timeout=aiohttp.ClientTimeout(total=self.cfg.timeout),
            )
            self.sessions.append(s)
        return self.sessions[0]

    async def run_clients(self, name: str, route: str, count: int, emails: list[str]):
        result = WsResult(name=name, clients=count)
        ws_url = self.cfg.ws_base_url.rstrip("/") + route
        session = await self._session()
        password = self.manifest.get("password", "")

        async def one_client(i: int):
            email = emails[i % len(emails)] if emails else None
            if not email:
                result.failed += 1
                result.errors.append("no seeded credentials for this role")
                return None
            sid, detail = await login(session, self.cfg.base_url, email, password)
            if not sid:
                result.failed += 1
                result.errors.append(f"login failed for {email}: {detail}")
                return None

            headers = {}
            if self.cfg.origin:
                headers["Origin"] = self.cfg.origin
            cookie_header = f"sessionid={sid}"
            for c in session.cookie_jar.filter_cookies(self.cfg.base_url):
                if c.key == "csrftoken":
                    cookie_header += f"; csrftoken={c.value}"
            headers["Cookie"] = cookie_header

            # Channels wraps the router in AllowedHostsOriginValidator
            # (adom/asgi.py:24). That validator compares the Origin header
            # against the request Host, and permits a *missing* Origin. Because
            # the benchmark pins ALLOWED_HOSTS to the tunnel hostname only, a
            # 127.0.0.1 Origin can be rejected -- so if a handshake is denied
            # we retry without Origin rather than reporting a false failure.
            attempts = [headers] if headers.get("Origin") else []
            attempts.append({k: v for k, v in headers.items() if k != "Origin"})

            t0 = time.perf_counter()
            last_exc: Exception | None = None
            for attempt in attempts:
                try:
                    ws = await websockets.connect(
                        ws_url, additional_headers=attempt, open_timeout=self.cfg.timeout
                    )
                    result.connected += 1
                    result.connect_ms.append((time.perf_counter() - t0) * 1000.0)
                    return ws
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if len(attempts) == 2:
                        result.failed += 1
                        msg = f"{type(exc).__name__}: {exc}"
                        if len(result.errors) < 5 and msg not in result.errors:
                            result.errors.append(msg)
                    continue
            if last_exc is not None and result.connected + result.failed == 0:
                result.failed += 1
            return None

        sockets = await asyncio.gather(*[one_client(i) for i in range(count)])
        return result, [s for s in sockets if s is not None]

    async def probe_notifications(self, clients: int) -> WsResult:
        """Connect N notification sockets and confirm they stay open."""
        emails = _emails(self.manifest, "student")
        result, sockets = await self.run_clients(
            "ws_notifications", "/ws/notifications/", clients, emails
        )
        if sockets:
            # The consumer accepts and then stays idle. Receiving nothing is the
            # success condition; a timeout means the socket is alive.
            async def drain(ws):
                try:
                    async with asyncio.timeout(3):
                        await ws.recv()
                except Exception:  # noqa: BLE001
                    pass

            await asyncio.gather(*[drain(ws) for ws in sockets], return_exceptions=True)
            for ws in sockets:
                await ws.close()
        return result

    async def probe_chat_fanout(self, clients: int) -> WsResult:
        """
        Connect N sockets to one chat room and measure true fan-out latency.

        Exactly one client sends; every client must receive. Time from the send
        to the last receipt is the number that matters for a school ("a parent
        gets the attendance alert"), so that is what is reported. Note that
        ChatConsumer persists every inbound message (consumers.py:142), so this
        probe writes Message rows -- intended, it makes write volume realistic.
        """
        emails = _emails(self.manifest, "student")
        room = "loadtestroom"
        result, sockets = await self.run_clients(
            "ws_chat_fanout", f"/ws/chat/{room}/", clients, emails
        )
        if len(sockets) < 2:
            return result

        # Every socket emits a join message on connect. Once those have settled,
        # one client sends a single broadcast and we time the fan-out.
        received: dict[int, int] = {i: 0 for i in range(len(sockets))}
        done = asyncio.Event()

        async def drain(idx: int, ws):
            try:
                while True:
                    async with asyncio.timeout(self.cfg.timeout):
                        await ws.recv()
                    received[idx] += 1
                    # 2 = the join message plus the broadcast we are timing.
                    if received[idx] >= 2 and all(v >= 2 for v in received.values()):
                        done.set()
            except Exception:  # noqa: BLE001 - timeout or close ends the drain
                return

        drains = [asyncio.create_task(drain(i, ws)) for i, ws in enumerate(sockets)]
        await asyncio.sleep(0.5)  # let the join messages land

        t0 = time.perf_counter()
        try:
            await sockets[0].send(json.dumps({"message": "load test broadcast"}))
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"send failed: {exc}")

        try:
            async with asyncio.timeout(self.cfg.timeout):
                await done.wait()
            result.fanout_ms.append((time.perf_counter() - t0) * 1000.0)
        except Exception:  # noqa: BLE001
            result.errors.append(
                f"fan-out timed out: {sum(1 for v in received.values() if v < 2)}"
                f"/{len(sockets)} sockets did not receive the broadcast"
            )

        result.messages_received = sum(received.values())
        for t in drains:
            t.cancel()
        await asyncio.gather(*drains, return_exceptions=True)
        for ws in sockets:
            await ws.close()
        return result

    async def close(self):
        for s in self.sessions:
            await s.close()


def _emails(manifest: dict, role: str) -> list[str]:
    """Seeded emails for a role. seed.py stores a list under tokens._emails."""
    return [e for e in manifest.get("tokens", {}).get("_emails", {}).get(role, []) if e]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", default=".colab_loadtest/manifest.json")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--ws-base-url", default="", help="Defaults to --base-url with ws:// scheme.")
    p.add_argument("--origin", default="",
                   help="Origin header. Leave empty to omit it: Channels' "
                        "AllowedHostsOriginValidator permits a missing Origin, "
                        "and the benchmark pins ALLOWED_HOSTS to the tunnel host only.")
    p.add_argument("--notifications", type=int, default=25)
    p.add_argument("--chat", type=int, default=25)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--out", default="ws_results.json")
    args = p.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    base = args.base_url
    ws_base = args.ws_base_url or re.sub(r"^http", "ws", base, count=1)
    origin = args.origin

    class Cfg:
        pass

    cfg = Cfg()
    cfg.base_url = base
    cfg.ws_base_url = ws_base
    cfg.origin = origin
    cfg.timeout = args.timeout

    print("=" * 90)
    print("ADOM Institute WebSocket probe (Django Channels)")
    print("=" * 90)
    print(f"  ws endpoint : {ws_base}/ws/notifications/ , {ws_base}/ws/chat/<room>/")
    print(f"  origin      : {origin or '(omitted - allowed by AllowedHostsOriginValidator)'}")
    print(f"  clients     : notifications={args.notifications}, chat={args.chat}")
    print()

    probe = WsProbe(cfg, manifest)

    async def run() -> list[WsResult]:
        results = [await probe.probe_notifications(args.notifications)]
        results.append(await probe.probe_chat_fanout(args.chat))
        return results

    try:
        results = asyncio.run(run())
    finally:
        pass

    print()
    print("=" * 90)
    print("WEBSOCKET RESULTS")
    print("=" * 90)
    print(
        f"  {'probe':<20}{'clients':>8}{'ok':>6}{'fail':>6}{'ok%':>8}"
        f"{'c-p50':>9}{'c-p95':>9}{'msgs':>7}{'fanout':>9}"
    )
    summaries = []
    for r in results:
        s = r.summary()
        summaries.append(s)
        print(
            f"  {s['name']:<20}{s['clients']:>8}{s['connected']:>6}{s['failed']:>6}"
            f"{s['connect_success_pct']:>8.1f}{s['connect_p50_ms']:>9.1f}"
            f"{s['connect_p95_ms']:>9.1f}{s['messages_received']:>7}{s['fanout_p50_ms']:>9.1f}"
        )
        for e in s["errors"]:
            print(f"      ! {e}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\n  raw results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
