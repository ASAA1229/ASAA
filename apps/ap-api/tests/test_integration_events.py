"""Ecosystem event ingestion (asaa.event.v1): validation, permissions, org binding, idempotency, secrets, audit."""
import json
import uuid
from pathlib import Path

import jsonschema
import pytest
from sqlalchemy import select

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal

ENVELOPE_SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "contracts" / "ecosystem" / "v1" / "event-envelope.schema.json").read_text())
WRITER = {"integration:event:write", "integration:event:read"}
URL = "/api/v1/integration/events"


def as_p(client, perms=WRITER, org="org-a", subject="svc-templates"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


def envelope(**over):
    base = {"specversion": "asaa.event.v1", "id": str(uuid.uuid4()), "source": "templates-api", "type": "templates.generation.completed",
            "time": "2026-11-18T10:00:00Z", "orgId": "org-a", "project": "TEMPLATES", "subject": "generation/abc",
            "correlationId": "corr-12345678", "severity": "info", "data": {"files": 3, "durationMs": 120}}
    base.update(over)
    return base


def test_fixture_envelope_matches_the_contract_schema():
    jsonschema.Draft202012Validator(ENVELOPE_SCHEMA, format_checker=jsonschema.FormatChecker()).validate(envelope())


def test_accepts_event_stores_it_and_writes_audit(client):
    as_p(client)
    body = envelope()
    response = client.post(URL, json=body, headers={"X-Correlation-ID": "audit-corr-1234"})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "accepted"
    listed = client.get(URL).json()
    assert [e["id"] for e in listed] == [body["id"]]
    assert listed[0]["received_by"] == "svc-templates" and listed[0]["organization_id"] == "org-a"
    session = next(client.app.dependency_overrides[get_db]())
    audit = session.scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.received")).all()
    assert len(audit) == 1 and audit[0].entity_id == body["id"] and audit[0].correlation_id == "audit-corr-1234"
    assert "data" not in audit[0].details


def test_same_id_same_content_is_duplicate_and_creates_no_second_row_or_audit(client):
    as_p(client)
    body = envelope()
    assert client.post(URL, json=body).json()["status"] == "accepted"
    again = client.post(URL, json=body)
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    assert len(client.get(URL).json()) == 1
    session = next(client.app.dependency_overrides[get_db]())
    assert len(session.scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.received")).all()) == 1
    # The same instant written with another offset is the same content.
    shifted = dict(body, time="2026-11-18T11:00:00+01:00")
    assert client.post(URL, json=shifted).json()["status"] == "duplicate"


def test_same_id_different_content_conflicts(client):
    as_p(client)
    body = envelope()
    client.post(URL, json=body)
    conflict = client.post(URL, json=dict(body, severity="critical"))
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "event_id_conflict"
    assert client.post(URL, json=dict(body, data={"files": 4})).status_code == 409


def test_event_id_used_by_another_org_conflicts_without_leaking(client):
    as_p(client, org="org-b")
    body = envelope(orgId="org-b")
    assert client.post(URL, json=body).status_code == 201
    as_p(client, org="org-a")
    clash = client.post(URL, json=dict(body, orgId="org-a"))
    assert clash.status_code == 409 and "org-b" not in clash.text
    assert client.get(URL).json() == []


def test_org_in_envelope_must_match_the_token_org(client):
    as_p(client, org="org-a")
    response = client.post(URL, json=envelope(orgId="org-b"))
    assert response.status_code == 403 and response.json()["detail"]["code"] == "event_org_mismatch"
    assert client.get(URL).json() == []


def test_permissions_are_enforced_separately_for_read_and_write(client):
    as_p(client, perms={"integration:event:read"})
    assert client.post(URL, json=envelope()).status_code == 403
    as_p(client, perms={"integration:event:write"})
    assert client.get(URL).status_code == 403
    as_p(client, perms=set())
    assert client.post(URL, json=envelope()).status_code == 403


def test_reads_are_scoped_to_the_callers_org(client):
    as_p(client, org="org-a")
    client.post(URL, json=envelope())
    as_p(client, org="org-b")
    assert client.get(URL).json() == []


@pytest.mark.parametrize("patch", [
    {"specversion": "asaa.event.v2"}, {"id": "not-a-uuid"}, {"source": "Bad Source"}, {"type": "unknown.thing.done"},
    {"type": "templates.only"}, {"time": "2026-11-18T10:00:00"}, {"time": "yesterday"}, {"project": "OTHER"}, {"severity": "fatal"},
    {"correlationId": "short"}, {"subject": "x" * 201}, {"orgId": ""}, {"data": "string"}, {"extra": 1},
])
def test_invalid_envelopes_are_rejected(client, patch):
    as_p(client)
    assert client.post(URL, json=envelope(**patch)).status_code == 422


def test_missing_required_fields_are_rejected(client):
    as_p(client)
    for key in ("specversion", "id", "source", "type", "time", "orgId", "project", "data"):
        body = envelope()
        body.pop(key)
        assert client.post(URL, json=body).status_code == 422, key


@pytest.mark.parametrize("data", [
    {"password": "x"}, {"nested": {"apiKey": "x"}}, {"items": [{"client_secret": "x"}]}, {"Authorization": "Bearer x"},
    {"api-key": "x"}, {"accessToken": "x"}, {"private_key": "x"},
])
def test_secret_looking_keys_are_rejected_without_echoing_values(client, data):
    as_p(client)
    response = client.post(URL, json=envelope(data=data))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "event_data_contains_secret_like_key"
    assert "Bearer" not in response.text
    assert client.get(URL).json() == []


def test_usage_counters_named_tokens_are_not_treated_as_secrets(client):
    as_p(client)
    response = client.post(URL, json=envelope(data={"prompt_tokens": 5, "completion_tokens": 7, "tokens_used": 12}))
    assert response.status_code == 201


def test_data_is_capped_at_16_kib(client):
    as_p(client)
    assert client.post(URL, json=envelope(data={"blob": "a" * (16 * 1024 - 20)})).status_code == 201
    response = client.post(URL, json=envelope(data={"blob": "a" * (16 * 1024)}))
    assert response.status_code == 422 and response.json()["detail"]["code"] == "event_data_too_large"


def test_list_filters_and_pagination(client):
    as_p(client)
    specs = [("templates-api", "templates.generation.completed", "TEMPLATES", "info", "2026-11-18T10:00:01Z"),
             ("jarvis", "jarvis.security.alert", "JARVIS", "critical", "2026-11-18T10:00:02Z"),
             ("jarvis", "jarvis.task.completed", "JARVIS", "info", "2026-11-18T10:00:03Z")]
    for source, kind, project, severity, when in specs:
        assert client.post(URL, json=envelope(source=source, type=kind, project=project, severity=severity, time=when)).status_code == 201
    everything = client.get(URL).json()
    assert [e["type"] for e in everything] == ["jarvis.task.completed", "jarvis.security.alert", "templates.generation.completed"]
    assert len(client.get(URL, params={"source": "jarvis"}).json()) == 2
    assert [e["type"] for e in client.get(URL, params={"type": "jarvis.security.alert"}).json()] == ["jarvis.security.alert"]
    assert len(client.get(URL, params={"project": "TEMPLATES"}).json()) == 1
    assert [e["severity"] for e in client.get(URL, params={"severity": "critical"}).json()] == ["critical"]
    assert len(client.get(URL, params={"limit": 2}).json()) == 2
    assert len(client.get(URL, params={"limit": 2, "offset": 2}).json()) == 1
    for bad in ({"limit": 0}, {"limit": 501}, {"offset": -1}, {"project": "NOPE"}, {"severity": "nope"}):
        assert client.get(URL, params=bad).status_code == 422


def test_unauthenticated_requests_are_rejected(client):
    client.app.dependency_overrides.pop(get_principal, None)
    assert client.post(URL, json=envelope()).status_code in {401, 503}
    assert client.get(URL).status_code in {401, 503}
