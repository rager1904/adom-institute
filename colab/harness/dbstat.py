#!/usr/bin/env python3
"""
PostgreSQL + Redis diagnostics for the seeded ADOM Institute dataset.

The load test tells you *that* something is slow. This tells you *why*. Three
sections:

1. **Table sizes.** Row counts and on-disk size per table, so you can tell a
   40k-row sequential scan (fine) from a 4M-row one (not fine).

2. **Index usage.** ``pg_stat_user_indexes`` shows indexes the planner has
   never touched. After a fresh seed almost everything is unused, which is
   expected -- run this *after* a load run for it to mean anything.

3. **EXPLAIN (ANALYZE, BUFFERS)** on the exact queries the read paths emit. The
   scoped teacher queries are the interesting ones: they join students, classes,
   schedules and teachers and then apply DISTINCT. A seq scan plus a large sort
   there is the finding that justifies a schema change.

Also reports the settings that matter under load (shared_buffers,
work_mem, max_connections) so you can compare Colab's defaults against
deploy/oci/postgres/postgresql.conf.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

TRACKED_TABLES = [
    ("students_student", "student"),
    ("students_parent", "parent"),
    ("attendance_attendance", "attendance"),
    ("academics_student_exam_result", "exam result"),
    ("academics_exam_subject", "exam subject"),
    ("academics_exam", "exam"),
    ("fees_student_fee", "student fee"),
    ("fees_payment", "payment"),
    ("fees_receipt", "receipt"),
    ("teachers_teacher", "teacher"),
    ("timetable_class_schedule", "class schedule"),
    ("timetable_time_slot", "time slot"),
    ("communication_notification", "notification"),
    ("communication_message", "message"),
    ("communication_message_recipient", "message recipient"),
    ("communication_communication_log", "comm log"),
    ("analytics_student_performance", "student performance"),
    ("analytics_analytics_event", "analytics event"),
    ("accounts_audit_log", "audit log"),
    ("auth_user", "user"),
    ("accounts_institution", "institution"),
    ("accounts_institution_membership", "membership"),
    ("auth_token", "api token"),
]

# The heavy reads, written out as the ORM would emit them.
EXPLAIN_QUERIES = [
    (
        "scoped students (teacher)  -- the tenant-scoped read path",
        """
        SELECT DISTINCT "students_student"."id"
        FROM "students_student"
        INNER JOIN "students_class" ON ("students_student"."current_class_id" = "students_class"."id")
        INNER JOIN "timetable_class_schedule" ON ("students_class"."id" = "timetable_class_schedule"."class_obj_id")
        INNER JOIN "teachers_teacher" ON ("timetable_class_schedule"."teacher_id" = "teachers_teacher"."id")
        WHERE "teachers_teacher"."user_id" = 1 AND "students_student"."is_active" = true
        """,
    ),
    (
        "scoped attendance (teacher) -- same join shape, largest table",
        """
        SELECT "attendance_attendance"."id", "attendance_attendance"."student_id", "attendance_attendance"."date"
        FROM "attendance_attendance"
        INNER JOIN "students_student" ON ("attendance_attendance"."student_id" = "students_student"."id")
        INNER JOIN "students_class" ON ("students_student"."current_class_id" = "students_class"."id")
        INNER JOIN "timetable_class_schedule" ON ("students_class"."id" = "timetable_class_schedule"."class_obj_id")
        WHERE "timetable_class_schedule"."teacher_id" IN (1, 2, 3)
        GROUP BY 1, 2, 3
        """,
    ),
    (
        "unscoped student list (platform admin) -- paginated, index or seq?",
        """
        SELECT "students_student"."id"
        FROM "students_student"
        WHERE "students_student"."is_active" = true
        ORDER BY "students_student"."id" DESC
        LIMIT 20
        """,
    ),
    (
        "student search (icontains) -- expect a seq scan, no trigram index",
        """
        SELECT "students_student"."id"
        FROM "students_student"
        WHERE "students_student"."student_id" LIKE '%10%'
        LIMIT 20
        """,
    ),
    (
        "overdue fees (accountant) -- index on (payment_status, due_date)",
        """
        SELECT "fees_student_fee"."id"
        FROM "fees_student_fee"
        WHERE "fees_student_fee"."payment_status" = 'overdue'
        ORDER BY "fees_student_fee"."due_date" ASC
        LIMIT 20
        """,
    ),
    (
        "attendance summary aggregate -- conditional COUNT over the whole table",
        """
        SELECT COUNT("attendance_attendance"."id"),
               COUNT("attendance_attendance"."id") FILTER (WHERE "attendance_attendance"."status" = 'present')
        FROM "attendance_attendance"
        WHERE "attendance_attendance"."date" >= CURRENT_DATE - 14
        """,
    ),
    (
        "notifications inbox (student) -- index on (recipient, status, created_at)",
        """
        SELECT "communication_notification"."id"
        FROM "communication_notification"
        WHERE "communication_notification"."recipient_id" = 1
          AND "communication_notification"."status" = 'read'
        ORDER BY "communication_notification"."created_at" DESC
        LIMIT 20
        """,
    ),
    (
        "class timetable (administrator) -- join class -> schedule -> slot",
        """
        SELECT "timetable_class_schedule"."id"
        FROM "timetable_class_schedule"
        INNER JOIN "timetable_time_slot"
                ON ("timetable_class_schedule"."time_slot_id" = "timetable_time_slot"."id")
        WHERE "timetable_class_schedule"."class_obj_id" = 1
        ORDER BY "timetable_time_slot"."day" ASC, "timetable_time_slot"."start_time" ASC
        """,
    ),
]

IMPORTANT_SETTINGS = [
    "shared_buffers",
    "effective_cache_size",
    "work_mem",
    "maintenance_work_mem",
    "max_connections",
    "random_page_cost",
    "effective_io_concurrency",
    "default_statistics_target",
    "max_parallel_workers_per_gather",
    "jit",
    "log_min_duration_statement",
]


def bootstrap(repo_root: Path) -> None:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adom.settings")
    import django

    django.setup()


def is_postgres() -> bool:
    from django.db import connection

    return "postgresql" in connection.settings_dict["ENGINE"]


# --------------------------------------------------------------------------- #

def section(title: str) -> None:
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


def query(cursor, sql: str, params=None):
    cursor.execute(sql, params or [])
    columns = [c[0] for c in cursor.description] if cursor.description else []
    return columns, cursor.fetchall()


def report_tables(cursor) -> list[dict]:
    cols, rows = query(
        cursor,
        """
        SELECT relname AS table,
               n_live_tup::bigint AS est_rows,
               pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
               pg_size_pretty(pg_table_size(c.oid)) AS table_size,
               pg_size_pretty(pg_indexes_size(c.oid)) AS index_size
        FROM pg_stat_user_tables s
        JOIN pg_class c ON c.oid = s.relid
        ORDER BY pg_total_relation_size(c.oid) DESC
        """,
    )
    return [dict(zip(cols, r)) for r in rows]


def report_settings(cursor) -> list[dict]:
    cols, rows = query(cursor, "SELECT name, setting, unit FROM pg_settings WHERE name = ANY(%s)",
                       [IMPORTANT_SETTINGS])
    return [dict(zip(cols, r)) for r in rows]


def report_unused_indexes(cursor, min_size_kb: int = 32) -> list[dict]:
    """
    Indexes the planner has never chosen. `idx_scan` is only meaningful if
    stats have been collected, which on a fresh seed they have not.
    """
    cols, rows = query(
        cursor,
        """
        SELECT s.relname AS table_name,
               s.indexrelname AS index_name,
               s.idx_scan::bigint AS scans,
               pg_size_pretty(pg_relation_size(s.indexrelid)) AS size,
               s.idx_tup_read::bigint AS tuples_read
        FROM pg_stat_user_indexes s
        WHERE s.idx_scan = 0
          AND pg_relation_size(s.indexrelid) > %s
        ORDER BY pg_relation_size(s.indexrelid) DESC
        LIMIT 25
        """,
        [min_size_kb * 1024],
    )
    return [dict(zip(cols, r)) for r in rows]


def report_cache_hit_ratio(cursor) -> dict:
    cols, rows = query(
        cursor,
        """
        SELECT sum(heap_blks_hit) AS hits,
               sum(heap_blks_read) AS reads
        FROM pg_statio_user_tables
        """,
    )
    d = dict(zip(cols, rows[0])) if rows else {}
    hits, reads = d.get("hits") or 0, d.get("reads") or 0
    total = hits + reads
    return {
        "heap_blocks_hit": int(hits),
        "heap_blocks_read": int(reads),
        "cache_hit_ratio_pct": round(hits / total * 100.0, 2) if total else None,
    }


def report_dead_tuples(cursor) -> list[dict]:
    cols, rows = query(
        cursor,
        """
        SELECT relname AS table,
               n_live_tup::bigint AS live,
               n_dead_tup::bigint AS dead,
               CASE WHEN n_live_tup > 0
                    THEN round((n_dead_tup::numeric / n_live_tup) * 100, 2)
                    ELSE 0 END AS dead_pct,
               last_autovacuum, last_autoanalyze
        FROM pg_stat_user_tables
        WHERE n_dead_tup > 0
        ORDER BY n_dead_tup DESC
        LIMIT 15
        """,
    )
    return [dict(zip(cols, r)) for r in rows]


def report_connections(cursor) -> dict:
    cols, rows = query(
        cursor,
        """
        SELECT state, count(*)::bigint AS n FROM pg_stat_activity
        WHERE datname = current_database() GROUP BY state
        """,
    )
    return {r[0]: int(r[1]) for r in rows}


def run_explain(cursor, label: str, sql: str) -> dict:
    # EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
    try:
        cursor.execute("EXPLAIN (ANALYZE, BUFFERS, TIMING) " + sql)
    except Exception as exc:  # noqa: BLE001
        return {"label": label, "error": f"{type(exc).__name__}: {exc}"}
    plan = [r[0] for r in cursor.fetchall()]

    text = "\n".join(plan)
    flags: list[str] = []
    if "Seq Scan" in text:
        flags.append("SEQ SCAN")
    if "Sort Method: external merge" in text or "Sort" in text and "Disk" in text:
        flags.append("EXTERNAL SORT (spilled to disk)")
    if "Batches:" in text and "Disk: 0kB" not in text:
        flags.append("HASH BATCHED (possible spill)")
    planning = execution = 0.0
    for row in plan:
        if "Planning Time" in row:
            planning = float(row.split(":")[-1].strip().split(" ")[0])
        if "Execution Time" in row:
            execution = float(row.split(":")[-1].strip().split(" ")[0])

    return {
        "label": label,
        "flags": flags,
        "planning_ms": planning,
        "execution_ms": execution,
        "plan": plan,
    }


# --------------------------------------------------------------------------- #

def report_redis(redis_url: str) -> dict | None:
    try:
        import redis as redis_lib
    except ImportError:
        return {"error": "redis python package not installed"}
    try:
        client = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=5)
        info = client.info()
        mem = info.get("memory", {})
        stats = info.get("stats", {})
        keyspace = info.get("keyspace", {})
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        return {
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "used_memory_human": mem.get("used_memory_human"),
            "used_memory_peak_human": mem.get("used_memory_peak_human"),
            "maxmemory_human": mem.get("maxmemory_human"),
            "evicted_keys": info.get("evicted_keys"),
            "expired_keys": info.get("expired_keys"),
            "keyspace_hits": hits,
            "keyspace_misses": misses,
            "cache_hit_ratio_pct": round(hits / total * 100.0, 2) if total else None,
            "keys_per_db": keyspace,
            "total_commands": stats.get("total_commands_processed"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=os.environ.get("ADOM_REPO", ""))
    p.add_argument("--redis-url", default=os.environ.get("REDIS_URL", ""))
    p.add_argument("--out", default="db_report.json")
    p.add_argument("--skip-explain", action="store_true")
    p.add_argument("--explain-only", action="store_true")
    args = p.parse_args()

    repo_root = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[2]
    bootstrap(repo_root)

    from django.db import connection

    if not is_postgres():
        print("This report is PostgreSQL-specific. Start Postgres and set DB_ENGINE=postgresql.")
        return 2

    report: dict = {}
    with connection.cursor() as cur:
        if not args.explain_only:
            section("TABLE SIZES")
            tables = report_tables(cur)
            report["tables"] = tables
            print(f"  {'table':<42}{'rows':>10}{'total':>12}{'table':>12}{'indexes':>12}")
            for t in tables:
                print(
                    f"  {t['table']:<42}{t['est_rows']:>10,}{t['total_size']:>12}"
                    f"{t['table_size']:>12}{t['index_size']:>12}"
                )
            total_rows = sum(t["est_rows"] for t in tables)
            print(f"  {'TOTAL':<42}{total_rows:>10,}")

            section("CACHE HIT RATIO (PostgreSQL buffer cache)")
            hit = report_cache_hit_ratio(cur)
            report["cache_hit"] = hit
            print(f"  heap blocks hit : {hit['heap_blocks_hit']:,}")
            print(f"  heap blocks read: {hit['heap_blocks_read']:,}")
            print(f"  hit ratio      : {hit['cache_hit_ratio_pct']}%")
            print(
                "  note: a low ratio on a freshly seeded database is expected --\n"
                "        nothing has been read twice yet. Re-run after a load test."
            )

            section("RELEVANT SERVER SETTINGS")
            settings_rows = report_settings(cur)
            report["settings"] = settings_rows
            for s in settings_rows:
                unit = f" {s['unit']}" if s.get("unit") else ""
                print(f"  {s['name']:<34} {s['setting']}{unit}")
            print(
                "\n  compare against deploy/oci/postgres/postgresql.conf; that file is\n"
                "  tuned for a 12 GB VM, which is close to a Colab standard runtime."
            )

            section("CONNECTIONS")
            conns = report_connections(cur)
            report["connections"] = conns
            for state, n in conns.items():
                print(f"  {state:<20} {n:>5}")
            print("  production uses PgBouncer in transaction mode to avoid connection storms")

            section("DEAD TUPLUES (autovacuum pressure)")
            dead = report_dead_tuples(cur)
            report["dead_tuples"] = dead
            if dead:
                print(f"  {'table':<40}{'live':>10}{'dead':>10}{'dead%':>8}  last_autovacuum")
                for d in dead:
                    print(
                        f"  {d['table']:<40}{d['live']:>10,}{d['dead']:>10,}"
                        f"{d['dead_pct']:>8}  {d['last_autovacuum']}"
                    )
            else:
                print("  none recorded yet (run after a write-heavy load test)")

            section("INDEXES WITH ZERO SCANS")
            unused = report_unused_indexes(cur)
            report["unused_indexes"] = unused
            if unused:
                print(f"  {'table':<40}{'index':<44}{'size':>10}")
                for u in unused:
                    print(f"  {u['table_name']:<40}{u['index_name']:<44}{u['size']:>10}")
                print(
                    "\n  Only meaningful AFTER a load run. On a fresh seed every index is\n"
                    "  unscanned by definition."
                )
            else:
                print("  none -- every index has been used at least once")

        if not args.skip_explain:
            section("EXPLAIN (ANALYZE, BUFFERS) -- the hot read paths")
            print(
                "  Each plan is the query the ORM emits for a live endpoint. Watch for\n"
                "  SEQ SCAN on a large table, EXTERNAL SORT (work_mem too small) and\n"
                "  high Batches counts (hash spilling).\n"
            )
            explains = []
            for label, sql in EXPLAIN_QUERIES:
                res = run_explain(cur, label, sql)
                explains.append(res)
                print()
                print(f"  --- {label}")
                if res.get("error"):
                    print(f"      ERROR: {res['error']}")
                    continue
                flags = ("  << " + ", ".join(res["flags"])) if res["flags"] else ""
                print(
                    f"      planning {res['planning_ms']:.2f} ms |"
                    f" execution {res['execution_ms']:.2f} ms{flags}"
                )
                for line in res["plan"]:
                    print(f"      {line}")
            report["explains"] = explains

        connection.close()

    if args.redis_url:
        section("REDIS")
        redis_report = report_redis(args.redis_url)
        report["redis"] = redis_report
        if redis_report.get("error"):
            print(f"  {redis_report['error']}")
        else:
            for k, v in redis_report.items():
                print(f"  {k:<26} {v}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n  full report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
