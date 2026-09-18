#!/usr/bin/env python3
"""Concurrent load against the read paths a logged-in student actually hits.

Why this exists
---------------
Every other check in this repo runs one request at a time. The failure this one
looks for only appears under concurrency: a query that is fine for the developer
clicking through the app, and quadratic for two hundred students on results day.
An N+1 does not surface as an error — it surfaces as a p95 that grows with the
size of a user's degree plan, which no unit test asserts on and no error tracker
reports.

It is deliberately read-only. Hammering the POST endpoints would exercise the
rate limiter (5/day on research, 10/hour on plans) rather than the database, and
would leave rows behind in whatever environment it was pointed at.

Usage
-----
    python scripts/loadtest.py --url http://127.0.0.1:8000 \
        --email you@example.com --password '...' --users 50 --requests 10

Exit code is non-zero when a threshold is breached, so it can gate a release.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time

import httpx

# A read that takes longer than this under load is the signal this script is for.
# Not a promise about production hardware — a tripwire for a query whose cost
# grows with concurrency or with a user's data, which is what an N+1 looks like
# from outside.
DEFAULT_P95_BUDGET_MS = 1500.0

# The endpoints a student's dashboard fans out to on one page load. These are the
# ones whose cost scales with how much a student has entered, which is exactly
# where an N+1 hides.
PATHS = [
    "/users/me",
    "/users/me/readiness",
    "/degree/summary",
    "/degree/gpa",
    "/degree/requirements",
    "/degree/courses",
    "/dashboard/weekly-summary",
    "/course-advisor/program-rules",
    "/health/ready",
]


async def login(base: str, email: str, password: str) -> httpx.Cookies:
    """Authenticate once and hand the cookies to every session.

    Not once per session, deliberately. `/auth/login` is rate-limited and bcrypt
    is intentionally expensive, so N concurrent logins measure the rate limiter
    and the KDF rather than the read paths this script is pointed at — the runs
    that did that spent their budget on 429s and reported a p95 for password
    hashing. N sessions sharing one identity is also the more honest model of
    the thing being tested: students who are *already* logged in, all loading
    their dashboard at once.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base}/auth/login",
            json={"email": email, "password": password},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        resp.raise_for_status()
        return client.cookies


async def hammer(
    client: httpx.AsyncClient, base: str, path: str, rounds: int
) -> tuple[list[float], list[int]]:
    latencies: list[float] = []
    failures: list[int] = []
    for _ in range(rounds):
        start = time.perf_counter()
        try:
            resp = await client.get(
                f"{base}{path}", headers={"X-Requested-With": "XMLHttpRequest"}
            )
            status = resp.status_code
        except httpx.HTTPError:
            status = 0
        latencies.append((time.perf_counter() - start) * 1000)
        # 429 is the rate limiter working correctly, not a failure of the app.
        if status not in (200, 429):
            failures.append(status)
    return latencies, failures


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * len(ordered))) - 1))
    return ordered[index]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--users", type=int, default=25, help="concurrent sessions")
    parser.add_argument(
        "--requests", type=int, default=5, help="requests per path per session"
    )
    parser.add_argument("--p95-budget-ms", type=float, default=DEFAULT_P95_BUDGET_MS)
    args = parser.parse_args()

    base = args.url.rstrip("/")
    print(f"load: {args.users} sessions x {args.requests} requests x {len(PATHS)} paths against {base}")

    cookies = await login(base, args.email, args.password)

    async def one_session():
        # A separate client per session, so this is N concurrent students rather
        # than one student issuing N requests — the connection pooling and
        # server-side concurrency behaviour differ.
        async with httpx.AsyncClient(timeout=30.0, cookies=cookies) as client:
            per_path: dict[str, list[float]] = {}
            failures: list[int] = []
            for path in PATHS:
                lat, fail = await hammer(client, base, path, args.requests)
                per_path[path] = lat
                failures.extend(fail)
            return per_path, failures

    # Warm the pool and the query planner first. Without this the very first
    # path measured absorbs every session's connection setup and reports a p95
    # that is really cold-start cost, which reads as a slow endpoint.
    async with httpx.AsyncClient(timeout=30.0, cookies=cookies) as warm:
        for path in PATHS:
            await warm.get(f"{base}{path}", headers={"X-Requested-With": "XMLHttpRequest"})

    started = time.perf_counter()
    results = await asyncio.gather(
        *(one_session() for _ in range(args.users)), return_exceptions=True
    )
    elapsed = time.perf_counter() - started

    crashed = [r for r in results if isinstance(r, Exception)]
    ok = [r for r in results if not isinstance(r, Exception)]
    if not ok:
        print(f"every session failed: {crashed[0] if crashed else 'unknown'}")
        return 1

    merged: dict[str, list[float]] = {}
    failures: list[int] = []
    for per_path, fails in ok:
        for path, lat in per_path.items():
            merged.setdefault(path, []).extend(lat)
        failures.extend(fails)

    total = sum(len(v) for v in merged.values())
    print(
        f"\n{len(ok)} sessions · {total} requests · {elapsed:.1f}s "
        f"· {total / elapsed:.0f} req/s\n"
    )
    print(f"{'path':<38} {'n':>5} {'median':>9} {'p95':>9} {'max':>9}")
    print("-" * 75)

    breached = []
    for path, lat in merged.items():
        p95 = percentile(lat, 95)
        flag = ""
        if p95 > args.p95_budget_ms:
            breached.append((path, p95))
            flag = "  <-- over budget"
        print(
            f"{path:<38} {len(lat):>5} {statistics.median(lat):>8.0f}ms "
            f"{p95:>8.0f}ms {max(lat):>8.0f}ms{flag}"
        )

    print()
    if crashed:
        print(f"FAIL: {len(crashed)} session(s) raised: {crashed[0]}")
    if failures:
        print(f"FAIL: {len(failures)} unexpected status codes: {sorted(set(failures))}")
    if breached:
        print(f"FAIL: {len(breached)} path(s) over the {args.p95_budget_ms:.0f}ms p95 budget.")
        print("      A p95 that grows with concurrency or with a user's data is the")
        print("      signature of an N+1 — check the query, not the hardware.")
    if not (crashed or failures or breached):
        print("PASS: no failures, every path inside the p95 budget.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
