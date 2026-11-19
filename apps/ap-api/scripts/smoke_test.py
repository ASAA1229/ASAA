#!/usr/bin/env python
"""Post-deployment smoke test (ASAA-010). Standard library only; safe to run against any environment.

  python scripts/smoke_test.py --base-url https://api.example.internal
  python scripts/smoke_test.py --base-url http://127.0.0.1:8001 --token-file token.txt --expect-production

Checks liveness, readiness (database), request-ID propagation, security headers, that API routes refuse
anonymous callers, that docs are not exposed in production, and (with a token) one authenticated read.
Read-only: it never creates or modifies data. Exit code 0 = all checks passed, 1 = at least one failed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def fetch(base: str, path: str, headers: dict | None = None, timeout: float = 10):
    request = urllib.request.Request(base.rstrip("/") + path, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def run(base: str, token: str | None, expect_production: bool) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    started = time.perf_counter()
    status, headers, body = fetch(base, "/health")
    check("liveness /health returns 200 ok", status == 200 and json.loads(body).get("status") == "ok", f"status={status}")
    check("liveness responds under 2s", time.perf_counter() - started < 2)

    status, headers, body = fetch(base, "/ready")
    check("readiness /ready reports database available", status == 200 and json.loads(body).get("database") == "available", f"status={status}")

    status, headers, _ = fetch(base, "/health", {"X-Request-ID": "smoke-test-0001"})
    lowered = {k.lower(): v for k, v in headers.items()}
    check("X-Request-ID is echoed", lowered.get("x-request-id") == "smoke-test-0001")
    check("security headers present", lowered.get("x-content-type-options") == "nosniff" and lowered.get("x-frame-options") == "DENY")

    status, headers, body = fetch(base, "/api/v1/ap/suppliers")
    check("anonymous API call is refused (401/503, never 200/500)", status in (401, 503), f"status={status}")
    check("API responses are not cacheable", {k.lower(): v for k, v in headers.items()}.get("cache-control") == "no-store")
    check("error body does not leak internals", b"Traceback" not in body and b"sqlalchemy" not in body.lower())

    status, _, _ = fetch(base, "/api/v1/ap/suppliers", {"Authorization": "Bearer not.a.jwt"})
    check("invalid bearer token is refused", status in (401, 503), f"status={status}")

    docs_status, _, _ = fetch(base, "/docs")
    if expect_production:
        check("API docs are disabled in production", docs_status == 404, f"status={docs_status}")
        metrics_status, _, _ = fetch(base, "/metrics")
        check("/metrics is not anonymously readable in production", metrics_status in (401, 404), f"status={metrics_status}")

    if token:
        status, _, body = fetch(base, "/api/v1/ap/suppliers?limit=1", {"Authorization": f"Bearer {token}"})
        check("authenticated read succeeds", status == 200, f"status={status}")
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--expect-production", action="store_true")
    args = parser.parse_args(argv)
    token = args.token_file.read_text().strip() if args.token_file else None
    try:
        results = run(args.base_url, token, args.expect_production)
    except (urllib.error.URLError, OSError) as exc:
        print(f"SMOKE FAIL: cannot reach {args.base_url}: {exc}", file=sys.stderr)
        return 1
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'  (' + detail + ')' if detail and not ok else ''}")
    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
