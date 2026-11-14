"""Minimal worker: python -m asaa_identity.worker [--once] [--interval 30]. Provider chosen by ASAA_AP_IDENTITY_PROVIDER."""
import argparse
import logging
import time

from asaa_ap.config import get_settings
from asaa_ap.database import SessionLocal
from asaa_identity import service
from asaa_identity.memory import InMemoryIdentityProvider
from asaa_identity.provider import register_provider, resolve_provider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    settings = get_settings()
    if settings.identity_provider == "memory" and settings.environment != "production":
        register_provider("memory", InMemoryIdentityProvider)
    provider = resolve_provider(settings.identity_provider)
    if provider is None:
        logging.getLogger("asaa.identity_sync").error("no_identity_provider_configured")
        return 2
    while True:
        with SessionLocal() as db:
            logging.getLogger("asaa.identity_sync").info("worker_cycle", extra=service.process_due(db, provider))
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
