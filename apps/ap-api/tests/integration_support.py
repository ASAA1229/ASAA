"""Shared helpers for ecosystem integration tests: producer mappings, settings and envelopes with a current timestamp."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from asaa_ap.config import Settings
from asaa_ap.database import get_db
from asaa_ap.security import Principal, get_principal
from asaa_integration import alerts, events

URL = "/api/v1/integration/events"
PRODUCERS = {
    "templates-events": {"source": "templates", "project": "TEMPLATES", "typePrefix": "templates."},
    "jarvis-events": {"source": "jarvis", "project": "JARVIS", "typePrefix": "jarvis."},
    "portfolio-events": {"source": "portfolio", "project": "PORTFOLIO", "typePrefix": "portfolio."},
}
WRITER = {"integration:event:write", "integration:event:read"}


def make_settings(**over):
    values = {"integration_producers": PRODUCERS, "integration_rate_per_minute": 6000, "integration_rate_burst": 1000}
    values.update(over)
    return Settings(**values)


def install_settings(monkeypatch, **over):
    settings = make_settings(**over)
    monkeypatch.setattr(events, "get_settings", lambda: settings)
    monkeypatch.setattr(alerts, "get_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def integration_settings(monkeypatch):
    events.reset_rate_limits()
    install_settings(monkeypatch)
    yield
    events.reset_rate_limits()


def as_producer(client, client_id="templates-events", org="org-a", perms=WRITER, subject=None):
    subject = subject or f"svc-{client_id}"
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms), client_id)


def now_iso(offset_seconds=0, tz=timezone.utc):
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=offset_seconds)).astimezone(tz).isoformat()


def envelope(**over):
    base = {"specversion": "asaa.event.v1", "id": str(uuid.uuid4()), "source": "templates", "type": "templates.generation.completed",
            "time": now_iso(), "orgId": "org-a", "project": "TEMPLATES", "subject": "generation/abc",
            "correlationId": "corr-12345678", "severity": "info", "data": {"files": 3, "durationMs": 120}}
    base.update(over)
    return base


def jarvis_envelope(**over):
    base = envelope(source="jarvis", type="jarvis.security.audit-integrity-failed", project="JARVIS", subject="audit/chain-7",
                    severity="critical", data={"brokenAt": 41})
    base.update(over)
    return base


def db_of(client):
    return next(client.app.dependency_overrides[get_db]())
