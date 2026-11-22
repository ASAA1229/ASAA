#!/usr/bin/env python
"""Retry sweep for ASAA ecosystem events that failed to stage (durable outbox retry).

  python scripts/retry_ecosystem_events.py                 # one pass
  python scripts/retry_ecosystem_events.py --interval 60   # worker mode

Runs outside business transactions. The database comes from ASAA_AP_DATABASE_URL or --database-url (a URL embedding a password is refused).
"""
from __future__ import annotations

import argparse
import sys
import time
from urllib.parse import urlparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--database-url", help="defaults to ASAA_AP_DATABASE_URL; must not embed a password")
    parser.add_argument("--interval", type=int, help="repeat every N seconds instead of running once")
    args = parser.parse_args(argv)
    if args.database_url and urlparse(args.database_url.replace("postgresql+psycopg://", "postgresql://", 1)).password:
        print("Refusing a database URL that embeds a password: use PGPASSWORD or the ASAA_AP_DATABASE_URL environment variable.", file=sys.stderr)
        return 2
    from asaa_ap.database import build_session_factory
    from asaa_integration import retry
    engine, factory = build_session_factory(args.database_url)
    try:
        while True:
            with factory() as session:
                print(retry.process_due(session))
            if not args.interval:
                return 0
            time.sleep(args.interval)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
