#!/usr/bin/env python
"""Reproducible local load / concurrency test for the ASAA API (ASAA-009).

Spawns a throw-away API process (uvicorn) on a free port with a generated RS256 key pair and
a fresh database (SQLite temp file by default, or --database-url for a disposable PostgreSQL),
applies migrations, then drives a mixed workload with N concurrent asyncio/httpx workers and
prints latency percentiles, throughput and error rate. Nothing external is contacted.

  python scripts/load_test.py --concurrency 20 --duration 20
  python scripts/load_test.py --database-url postgresql+psycopg://user:pw@127.0.0.1:55432/asaa_load --workers 2
  python scripts/load_test.py --base-url https://staging.example --token-file token.txt   (existing deployment; no spawn)

Results measure THIS machine and database only. They are not production capacity evidence.
Exit status is 1 if the error rate or --p95-budget-ms budget is exceeded.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ISSUER, AUDIENCE = "https://load-test.invalid", "asaa-load-test"
PERMISSIONS = ["supplier:read", "supplier:write", "supplier:status", "audit:read", "ar:customer:read", "ar:customer:write"]


def free_port() -> int:
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return key, public


def sign(key, org: str) -> str:
    import jwt
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": "load-user", "org_id": org, "iss": ISSUER, "aud": AUDIENCE, "iat": now,
                       "exp": now + timedelta(hours=2), "permissions": PERMISSIONS}, key, algorithm="RS256")


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return float("nan")
    index = min(len(sorted_values) - 1, max(0, int(round(p / 100 * len(sorted_values) + 0.5)) - 1))
    return sorted_values[index]


async def worker(client: httpx.AsyncClient, headers: dict, deadline: float, mix, samples: dict, errors: dict):
    while time.perf_counter() < deadline:
        name, method, path, body = random.choices(mix, weights=[m[0] for m in mix])[0][1:]
        if callable(body):
            body = body()
        started = time.perf_counter()
        try:
            response = await client.request(method, path, json=body, headers=headers)
            ok = response.status_code < 400
            code = response.status_code
        except httpx.HTTPError as exc:
            ok, code = False, type(exc).__name__
        samples.setdefault(name, []).append((time.perf_counter() - started) * 1000)
        if not ok:
            errors[f"{name}:{code}"] = errors.get(f"{name}:{code}", 0) + 1


def workload():
    def supplier():
        unique = uuid.uuid4().hex[:12]
        return {"legal_name": f"Load Supplier {unique}", "email": f"{unique}@load.invalid"}
    return [
        (5, "health", "GET", "/health", None),
        (5, "ready", "GET", "/ready", None),
        (55, "list_suppliers", "GET", "/api/v1/ap/suppliers?limit=50", None),
        (25, "create_supplier", "POST", "/api/v1/ap/suppliers", supplier),
        (10, "audit_events", "GET", "/api/v1/ap/audit-events?limit=50", None),
    ]


def summarize(samples: dict, elapsed: float, errors: dict) -> dict:
    rows, every = {}, []
    for name, values in sorted(samples.items()):
        ordered = sorted(values)
        every.extend(values)
        rows[name] = {"count": len(ordered), "p50_ms": round(percentile(ordered, 50), 1), "p90_ms": round(percentile(ordered, 90), 1),
                      "p95_ms": round(percentile(ordered, 95), 1), "p99_ms": round(percentile(ordered, 99), 1), "max_ms": round(ordered[-1], 1)}
    ordered = sorted(every)
    total = len(ordered)
    failed = sum(errors.values())
    return {"requests": total, "duration_s": round(elapsed, 2), "throughput_rps": round(total / elapsed, 1),
            "error_count": failed, "error_rate": round(failed / total, 4) if total else 1.0, "errors": errors,
            "overall": {"mean_ms": round(statistics.fmean(ordered), 1), "p50_ms": round(percentile(ordered, 50), 1),
                        "p90_ms": round(percentile(ordered, 90), 1), "p95_ms": round(percentile(ordered, 95), 1),
                        "p99_ms": round(percentile(ordered, 99), 1), "max_ms": round(ordered[-1], 1)},
            "by_operation": rows}


async def run_load(base_url: str, token: str, concurrency: int, duration: float, warmup: float = 2.0) -> dict:
    limits = httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency + 5)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
        await asyncio.gather(*[worker(client, headers, time.perf_counter() + warmup, workload(), {}, {}) for _ in range(min(concurrency, 4))])
        samples, errors = {}, {}
        started = time.perf_counter()
        deadline = started + duration
        await asyncio.gather(*[worker(client, headers, deadline, workload(), samples, errors) for _ in range(concurrency)])
        return summarize(samples, time.perf_counter() - started, errors)


def spawn_api(database_url: str | None, workers: int, tmp: Path, migrate_url: str | None = None):
    key, public = make_keys()
    port = free_port()
    url = database_url or f"sqlite:///{(tmp / 'load.db').as_posix()}"
    env = {**os.environ, "ASAA_AP_DATABASE_URL": url, "ASAA_AP_ENVIRONMENT": "test", "ASAA_AP_JWT_PUBLIC_KEY": public,
           "ASAA_AP_JWT_ISSUER": ISSUER, "ASAA_AP_JWT_AUDIENCE": AUDIENCE, "ASAA_AP_LOG_LEVEL": "WARNING"}
    migrate_env = {**env, "ASAA_AP_DATABASE_URL": migrate_url} if migrate_url else env
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=migrate_env, check=True, capture_output=True)
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "asaa_ap.main:app", "--host", "127.0.0.1", "--port", str(port),
                                "--workers", str(workers), "--log-level", "warning"], cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            if httpx.get(base + "/ready", timeout=2).status_code == 200:
                return process, base, sign(key, f"load-org-{uuid.uuid4().hex[:6]}"), url
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    process.kill()
    raise SystemExit("API did not become ready")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=float, default=20.0, help="seconds")
    parser.add_argument("--workers", type=int, default=1, help="uvicorn worker processes (spawned API only)")
    parser.add_argument("--database-url", help="disposable database for the spawned API (default: temp SQLite)")
    parser.add_argument("--base-url", help="test an already running API instead of spawning one")
    parser.add_argument("--token-file", help="bearer token for --base-url")
    parser.add_argument("--p95-budget-ms", type=float, help="fail if overall p95 exceeds this")
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    process = None
    tmp = tempfile.TemporaryDirectory()
    try:
        if args.base_url:
            base, token, db_label = args.base_url, Path(args.token_file).read_text().strip(), "external"
        else:
            process, base, token, db_label = spawn_api(args.database_url, args.workers, Path(tmp.name))
            db_label = "postgresql" if db_label.startswith("postgresql") else "sqlite"
        result = asyncio.run(run_load(base, token, args.concurrency, args.duration))
        result["environment"] = {"python": platform.python_version(), "os": platform.platform(), "cpus": os.cpu_count(),
                                 "database": db_label, "api_workers": args.workers if process else None,
                                 "concurrency": args.concurrency, "target": "local spawned API" if process else base}
        print(json.dumps(result, indent=2))
        if args.json_out:
            args.json_out.write_text(json.dumps(result, indent=2))
        failed = result["error_rate"] > args.max_error_rate
        if args.p95_budget_ms and result["overall"]["p95_ms"] > args.p95_budget_ms:
            print(f"BUDGET EXCEEDED: p95 {result['overall']['p95_ms']} ms > {args.p95_budget_ms} ms", file=sys.stderr)
            failed = True
        if result["error_rate"] > args.max_error_rate:
            print(f"ERROR RATE {result['error_rate']:.2%} exceeds {args.max_error_rate:.2%}", file=sys.stderr)
        return 1 if failed else 0
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            tmp.cleanup()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
