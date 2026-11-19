"""Producer mapping validation and shipped defaults, alert flood protection, bounded alert keys, scheduled retention."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from sqlalchemy import select

from asaa_ap.config import Settings
from asaa_integration import alerts
from asaa_notifications.models import NotificationMessage
from tests.integration_support import (URL, as_producer, db_of, install_settings, integration_settings, jarvis_envelope)  # noqa: F401
from tests.test_integration_alerts import grant

REPO = Path(__file__).resolve().parents[3]
EXPECTED_PRODUCERS = {
    "jarvis-events": {"source": "jarvis", "project": "JARVIS", "typePrefix": "jarvis."},
    "portfolio-events": {"source": "portfolio", "project": "PORTFOLIO", "typePrefix": "portfolio."},
    "templates-events": {"source": "templates", "project": "TEMPLATES", "typePrefix": "templates."},
}


def producer(**over):
    return {"x-events": {"source": "jarvis", "project": "JARVIS", "typePrefix": "jarvis.", **over}}


# ------------------------------------------------------------------------------------ producer mapping validation

def test_valid_mappings_are_accepted():
    assert set(Settings(integration_producers=EXPECTED_PRODUCERS).integration_producers) == set(EXPECTED_PRODUCERS)


@pytest.mark.parametrize("bad", [
    {"typePrefix": ""}, {"typePrefix": "jarvis"}, {"typePrefix": "jarvis.task"}, {"typePrefix": "other."}, {"typePrefix": "."},
    {"typePrefix": "jarvis-x."}, {"project": "OTHER"}, {"project": "jarvis"}, {"source": ""}, {"source": "J"}, {"source": "Jarvis", "typePrefix": "Jarvis."},
    {"source": "jarvis ", "typePrefix": "jarvis ."}, {"extra": "field"},
])
def test_invalid_mappings_are_rejected_at_startup(bad):
    with pytest.raises(ValidationError):
        Settings(integration_producers=producer(**bad))


def test_two_clients_cannot_share_a_source_or_a_prefix_and_client_ids_are_validated():
    twin = {"a-events": EXPECTED_PRODUCERS["jarvis-events"], "b-events": EXPECTED_PRODUCERS["jarvis-events"]}
    with pytest.raises(ValidationError):
        Settings(integration_producers=twin)
    with pytest.raises(ValidationError):
        Settings(integration_producers={"bad id!": EXPECTED_PRODUCERS["jarvis-events"]})
    with pytest.raises(ValidationError):
        Settings(integration_producers={"": EXPECTED_PRODUCERS["jarvis-events"]})


def test_the_producers_setting_is_read_from_its_documented_environment_variable(monkeypatch):
    monkeypatch.setenv("ASAA_AP_INTEGRATION_PRODUCERS", json.dumps(EXPECTED_PRODUCERS))
    assert Settings().integration_producers["jarvis-events"].typePrefix == "jarvis."
    monkeypatch.setenv("ASAA_AP_INTEGRATION_PRODUCERS", json.dumps(producer(typePrefix="nope")))
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("compose", ["deploy/docker-compose.yml", "deploy/local-prod/docker-compose.yml"])
def test_deployment_configuration_ships_the_three_ecosystem_producers(compose):
    document = yaml.safe_load((REPO / compose).read_text())
    configured = json.loads(document["services"]["api"]["environment"]["ASAA_AP_INTEGRATION_PRODUCERS"])
    assert configured == EXPECTED_PRODUCERS
    Settings(integration_producers=configured)  # passes the startup validation


# ------------------------------------------------------------------------------------ alert flood protection

def critical(kind, **over):
    return jarvis_envelope(type=f"jarvis.security.{kind}", **over)


def messages(client):
    return db_of(client).scalars(select(NotificationMessage)).all()


@pytest.fixture
def jarvis(client):
    as_producer(client, "jarvis-events")
    grant(db_of(client), "alice", ["integration:event:read"])
    return client


def test_varying_type_names_cannot_flood_recipients(jarvis):
    for kind in ("one", "two", "three", "four", "five", "six"):
        assert jarvis.post(URL, json=critical(kind)).status_code == 201
    assert len(messages(jarvis)) == 3  # source_max_streams default: three distinct alert streams per window
    assert jarvis.post(URL, json=critical("one")).status_code == 201
    assert len(messages(jarvis)) == 3


def test_the_stream_cap_is_per_source_and_configurable(jarvis, monkeypatch):
    install_settings(monkeypatch, integration_critical_source_max_streams=1)
    jarvis.post(URL, json=critical("one"))
    jarvis.post(URL, json=critical("two"))
    assert len(messages(jarvis)) == 1
    as_producer(jarvis, "portfolio-events")  # another source has its own budget
    grant(db_of(jarvis), "bob", ["integration:event:read"])
    from tests.integration_support import envelope
    assert jarvis.post(URL, json=envelope(source="portfolio", project="PORTFOLIO", type="portfolio.security.breach", severity="critical")).status_code == 201
    assert len(messages(jarvis)) == 3  # alice + bob get the portfolio alert (one stream each) on top of the first jarvis alert


def test_the_window_expiry_reopens_the_streams(jarvis):
    for kind in ("one", "two", "three"):
        jarvis.post(URL, json=critical(kind))
    session = db_of(jarvis)
    for message in session.scalars(select(NotificationMessage)).all():
        message.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.commit()
    jarvis.post(URL, json=critical("four"))
    assert len(messages(jarvis)) == 4


# ------------------------------------------------------------------------------------ bounded idempotency keys

def test_idempotency_keys_stay_under_the_column_limit_for_maximum_length_types_and_recipients(client, monkeypatch):
    as_producer(client, "jarvis-events")
    long_recipient = "r" * 128
    install_settings(monkeypatch, integration_critical_recipients=[long_recipient, "s" * 128])
    long_type = "jarvis.security." + "-".join(["segment"] * 12)
    long_type = long_type[:120]
    assert len(long_type) == 120 or len(long_type) > 100
    response = client.post(URL, json=jarvis_envelope(type=long_type, source="jarvis", subject="a" * 200))
    assert response.status_code == 201, response.text
    stored = messages(client)
    assert len(stored) == 2 and {m.recipient_subject for m in stored} == {long_recipient, "s" * 128}
    assert all(len(m.idempotency_key) < 200 for m in stored)
    assert len({m.idempotency_key for m in stored}) == 2  # distinct recipients never collide after hashing


def test_alert_keys_are_stable_and_unique_per_event_and_recipient():
    prefix = alerts.alert_key_prefix("jarvis", "jarvis.security.x")
    assert prefix == alerts.alert_key_prefix("jarvis", "jarvis.security.x") and prefix != alerts.alert_key_prefix("jarvis", "jarvis.security.y")
    assert alerts.alert_key_prefix("jarvis").endswith("jarvis:") and alerts.alert_key_prefix("jarvis", "t").startswith("integration.critical:jarvis:")
    assert alerts._digest("a") != alerts._digest("b") and len(alerts._digest("a" * 10000)) == 16


# ------------------------------------------------------------------------------------ scheduled retention

def test_local_prod_schedules_the_retention_purge_with_a_configurable_default_of_180_days():
    document = yaml.safe_load((REPO / "deploy/local-prod/docker-compose.yml").read_text())
    service = document["services"]["integration-retention"]
    assert service["command"][:2] == ["python", "scripts/purge_integration_events.py"] and "--interval" in service["command"]
    assert service["environment"]["ASAA_AP_INTEGRATION_EVENT_RETENTION_DAYS"] == "${ASAA_INTEGRATION_RETENTION_DAYS:-180}"
    assert service["image"] == document["services"]["api"]["image"] and service["restart"] == "unless-stopped"
    assert service["read_only"] is True and service["cap_drop"] == ["ALL"] and "ports" not in service
