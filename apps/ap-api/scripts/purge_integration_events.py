#!/usr/bin/env python
"""Retention purge for ingested ecosystem events (integration_events).

  python scripts/purge_integration_events.py                 # one pass using ASAA_AP_INTEGRATION_EVENT_RETENTION_DAYS (default 180)
  python scripts/purge_integration_events.py --days 90 --dry-run
  python scripts/purge_integration_events.py --interval 3600  # worker mode: repeat every hour

The default retention period (180 days) is owner-approved and configurable; nothing schedules this script.
A purge writes one audit event per organization with the number of rows removed (never their content). The database comes from
ASAA_AP_DATABASE_URL or --database-url (a URL that embeds a password is refused: use the environment).
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import delete, func, select


def purge(session, days: int, now: datetime | None = None, dry_run: bool = False) -> dict[str, int]:
    """Delete events received more than `days` days ago. Returns {organization_id: rows} (rows that were, or in a dry run would be, removed)."""
    from asaa_ap.models import AuditEvent
    from asaa_integration.models import IntegrationEvent

    if days < 1:
        raise ValueError("retention days must be at least 1")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    counts = dict(session.execute(select(IntegrationEvent.organization_id, func.count()).where(IntegrationEvent.received_at < cutoff)
                                  .group_by(IntegrationEvent.organization_id)).all())
    if counts and not dry_run:
        session.execute(delete(IntegrationEvent).where(IntegrationEvent.received_at < cutoff))
        for org, rows in counts.items():
            session.add(AuditEvent(organization_id=org, actor_id="system:integration-retention", action="integration_event.purged",
                                   entity_type="integration_event", entity_id="-",
                                   details={"rows": rows, "retention_days": days, "cutoff": cutoff.isoformat()}))
        session.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, help="retention in days (default: ASAA_AP_INTEGRATION_EVENT_RETENTION_DAYS)")
    parser.add_argument("--database-url", help="defaults to ASAA_AP_DATABASE_URL; must not embed a password")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interval", type=int, help="repeat every N seconds instead of running once")
    args = parser.parse_args(argv)
    if args.database_url and urlparse(args.database_url.replace("postgresql+psycopg://", "postgresql://", 1)).password:
        print("Refusing a database URL that embeds a password: use PGPASSWORD or the ASAA_AP_DATABASE_URL environment variable.", file=sys.stderr)
        return 2
    from asaa_ap.config import get_settings
    from asaa_ap.database import build_session_factory
    days = args.days or get_settings().integration_event_retention_days
    engine, factory = build_session_factory(args.database_url)
    try:
        while True:
            with factory() as session:
                counts = purge(session, days, dry_run=args.dry_run)
            prefix = "[dry run] would remove" if args.dry_run else "removed"
            print(f"{prefix} {sum(counts.values())} event(s) older than {days} day(s) from {len(counts)} organization(s)")
            if not args.interval:
                return 0
            time.sleep(args.interval)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
