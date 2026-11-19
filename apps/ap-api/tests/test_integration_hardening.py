"""Hardening of ecosystem event ingestion: producer binding, severity policy, quotas, streamed-body limits, payload screening,
per-organization ids, timestamp validation and audited rejections."""
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

import asaa_ap.security as security
from asaa_ap.hardening import HardeningMiddleware
from asaa_ap.models import AuditEvent
from asaa_integration import events, screening
from asaa_integration.models import IntegrationEvent
from asaa_notifications.models import NotificationMessage
from tests.integration_support import (URL, as_producer, db_of, envelope, install_settings, integration_settings,  # noqa: F401
                                       jarvis_envelope, now_iso)
from tests.test_integration_alerts import grant

HEADERS = {"Content-Type": "application/json"}


def raw_post(client, body: bytes, headers=None):
    return client.post(URL, content=body, headers={**HEADERS, **(headers or {})})


def rejections(client):
    return db_of(client).scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.rejected")
                                 .order_by(AuditEvent.created_at)).all()


@pytest.fixture(autouse=True)
def writer(client):
    as_producer(client)


# ------------------------------------------------------------------------------------ producer binding

def test_a_token_without_a_mapped_azp_cannot_write(client):
    for client_id in (None, "some-other-client", ""):
        as_producer(client, client_id)
        response = client.post(URL, json=envelope())
        assert response.status_code == 403 and response.json()["detail"]["code"] == "producer_not_authorized", client_id
    assert client.get(URL).json() == []


def test_no_configured_producers_means_nobody_can_write(client, monkeypatch):
    install_settings(monkeypatch, integration_producers={})
    assert client.post(URL, json=envelope()).json()["detail"]["code"] == "producer_not_authorized"


@pytest.mark.parametrize("patch", [
    {"source": "jarvis"}, {"project": "JARVIS"}, {"type": "jarvis.task.completed"}, {"type": "ci.build.completed"},
    {"source": "templates2"},
])
def test_envelope_must_match_the_producer_mapping(client, patch):
    response = client.post(URL, json=envelope(**patch))
    assert response.status_code == 403 and response.json()["detail"]["code"] == "producer_mismatch", patch
    assert client.get(URL).json() == []


def test_each_producer_can_only_speak_for_itself(client):
    as_producer(client, "jarvis-events")
    assert client.post(URL, json=jarvis_envelope(severity="info")).status_code == 201
    assert client.post(URL, json=envelope()).json()["detail"]["code"] == "producer_mismatch"
    as_producer(client, "portfolio-events")
    assert client.post(URL, json=envelope(source="portfolio", project="PORTFOLIO", type="portfolio.page.published")).status_code == 201
    assert client.post(URL, json=jarvis_envelope(severity="info")).json()["detail"]["code"] == "producer_mismatch"


def test_org_in_envelope_must_match_the_token_org(client):
    response = client.post(URL, json=envelope(orgId="org-b"))
    assert response.status_code == 403 and response.json()["detail"]["code"] == "event_org_mismatch"
    assert client.get(URL).json() == []


def test_azp_is_read_from_the_verified_token(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    settings = SimpleNamespace(jwt_public_key=public, jwt_jwks_url=None, jwt_issuer="https://issuer.example", jwt_audience="asaa-api",
                               jwt_algorithm="RS256", jwt_leeway_seconds=0, required_acr=None, required_amr=None)
    monkeypatch.setattr(security, "get_settings", lambda: settings)

    def token(**extra):
        claims = {"sub": "svc", "org_id": "org-a", "iss": "https://issuer.example", "aud": "asaa-api", "permissions": ["integration:event:write"],
                  "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **extra}
        return "Bearer " + jwt.encode(claims, key, algorithm="RS256")

    assert security.get_principal(token(azp="jarvis-events")).client_id == "jarvis-events"
    assert security.get_principal(token()).client_id is None
    assert security.get_principal(token(azp=["not", "a", "string"])).client_id is None


# ------------------------------------------------------------------------------------ severity policy

def test_only_security_types_may_be_critical_and_both_severities_are_stored(client):
    as_producer(client, "jarvis-events")
    capped = client.post(URL, json=jarvis_envelope(type="jarvis.task.completed")).json()["event"]
    assert (capped["severity"], capped["declared_severity"]) == ("warning", "critical")
    kept = client.post(URL, json=jarvis_envelope(type="jarvis.security.audit-integrity-failed")).json()["event"]
    assert (kept["severity"], kept["declared_severity"]) == ("critical", "critical")
    info = client.post(URL, json=jarvis_envelope(type="jarvis.task.completed", severity="info")).json()["event"]
    assert (info["severity"], info["declared_severity"]) == ("info", "info")
    assert [e["type"] for e in client.get(URL, params={"severity": "critical"}).json()] == ["jarvis.security.audit-integrity-failed"]


@pytest.mark.parametrize("kind,expected", [("jarvis.security.alert", "critical"), ("jarvis.security.audit.failed", "critical"),
                                           ("jarvis.task.security", "warning"), ("jarvis.securityx.alert", "warning"),
                                           ("jarvis.task.completed", "warning")])
def test_severity_policy_function(kind, expected):
    assert events.effective_severity(kind, "critical") == expected
    assert events.effective_severity(kind, "info") == "info"


def test_a_capped_critical_event_raises_no_notification(client):
    as_producer(client, "jarvis-events")
    grant(db_of(client), "alice", ["integration:event:read"])
    assert client.post(URL, json=jarvis_envelope(type="jarvis.task.completed")).status_code == 201
    assert db_of(client).scalars(select(NotificationMessage)).all() == []


def test_a_resent_event_with_a_different_declared_severity_conflicts(client):
    as_producer(client, "jarvis-events")
    body = jarvis_envelope(type="jarvis.task.completed")
    assert client.post(URL, json=body).status_code == 201
    assert client.post(URL, json=dict(body, severity="warning")).status_code == 409
    assert client.post(URL, json=body).json()["status"] == "duplicate"


# ------------------------------------------------------------------------------------ rate limit

def test_per_principal_token_bucket(client, monkeypatch):
    install_settings(monkeypatch, integration_rate_per_minute=6, integration_rate_burst=3)
    clock = [1000.0]
    monkeypatch.setattr(events, "_now", lambda: clock[0])
    assert [client.post(URL, json=envelope()).status_code for _ in range(3)] == [201, 201, 201]
    limited = client.post(URL, json=envelope())
    assert limited.status_code == 429 and limited.json()["detail"]["code"] == "event_rate_limited"
    assert 1 <= int(limited.headers["retry-after"]) <= 10
    as_producer(client, "jarvis-events")  # another principal has its own bucket
    assert client.post(URL, json=jarvis_envelope(severity="info")).status_code == 201
    as_producer(client)
    clock[0] += 10.0  # 6/min = one token per 10 s
    assert client.post(URL, json=envelope()).status_code == 201
    assert client.post(URL, json=envelope()).status_code == 429
    clock[0] += 3600.0  # refill is capped at the burst size
    assert [client.post(URL, json=envelope()).status_code for _ in range(4)] == [201, 201, 201, 429]


def test_rate_limited_requests_are_not_parsed_or_stored(client, monkeypatch):
    install_settings(monkeypatch, integration_rate_per_minute=1, integration_rate_burst=1)
    assert client.post(URL, json=envelope()).status_code == 201
    assert raw_post(client, b"{not json").status_code == 429
    assert len(client.get(URL).json()) == 1


def test_permission_is_checked_before_the_rate_limit(client, monkeypatch):
    install_settings(monkeypatch, integration_rate_per_minute=1, integration_rate_burst=1)
    as_producer(client, perms={"integration:event:read"})
    assert [client.post(URL, json=envelope()).status_code for _ in range(3)] == [403, 403, 403]


# ------------------------------------------------------------------------------------ depth, NaN, numbers

def nested(depth):
    value = {"leaf": 1}
    for _ in range(depth):
        value = {"n": value}
    return value


def test_deep_nesting_is_rejected_before_validation(client):
    ok = client.post(URL, json=envelope(data=nested(5)))
    assert ok.status_code == 201
    deep = client.post(URL, json=envelope(data=nested(40)))
    assert deep.status_code == 422 and deep.json()["detail"]["code"] == "event_too_deeply_nested"


def test_pathological_nesting_never_causes_a_500(client):
    for body in (b'{"data":' + b"[" * 4000 + b"]" * 4000 + b"}", b'{"a":' * 3000 + b"1" + b"}" * 3000):
        response = raw_post(client, body)
        assert response.status_code == 422 and response.json()["detail"]["code"] in {"invalid_json", "event_too_deeply_nested"}


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_non_finite_numbers_are_rejected(client, literal):
    body = json.dumps(envelope(data={"marker": 1})).replace('"marker": 1', f'"marker": {literal}').encode()
    response = raw_post(client, body)
    assert response.status_code == 422 and response.json()["detail"]["code"] in {"invalid_json", "event_data_non_finite_number"}
    assert client.get(URL).json() == []


def test_invalid_json_and_non_object_bodies_are_422_not_500(client):
    for body in (b"", b"{", b"[]", b"null", b'"text"', b"\xff\xfe"):
        assert raw_post(client, body).status_code == 422, body


def test_validation_errors_never_echo_submitted_values(client):
    response = client.post(URL, json=envelope(severity="sk-live-0123456789abcdef0123", orgId="x" * 500))
    assert response.status_code == 422
    assert "sk-live" not in response.text and "xxxxxxxx" not in response.text
    assert set(response.json()["detail"]["fields"]) == {"severity", "orgId"}


# ------------------------------------------------------------------------------------ screening through the endpoint


def test_screening_reaches_values_inside_lists_and_nested_objects(client):
    for data in ({"items": [{"note": "ghp_" + "a" * 36}]}, {"a": {"b": {"c": "https://u:p@h/x"}}}, {"list": ["AKIAABCDEFGHIJKLMNOP"]}):
        response = client.post(URL, json=envelope(data=data))
        assert response.status_code == 422 and response.json()["detail"]["code"] == "event_data_contains_secret_like_content"
        assert "ghp_" not in response.text and "AKIA" not in response.text and "u:p@" not in response.text


# ------------------------------------------------------------------------------------ per-organization ids

def test_event_ids_are_scoped_to_the_organization(client):
    shared = str(uuid.uuid4())
    as_producer(client, org="org-a")
    first = client.post(URL, json=envelope(id=shared, orgId="org-a"))
    as_producer(client, org="org-b")
    second = client.post(URL, json=envelope(id=shared, orgId="org-b", data={"files": 99}))
    assert (first.status_code, second.status_code) == (201, 201)  # no cross-org collision, no 409 oracle
    assert [e["data"] for e in client.get(URL).json()] == [{"files": 99}]
    as_producer(client, org="org-a")
    assert [e["data"] for e in client.get(URL).json()] == [{"files": 3, "durationMs": 120}]
    assert client.post(URL, json=envelope(id=shared, orgId="org-a", data={"files": 1})).status_code == 409  # conflict only within the org
    assert client.post(URL, json=envelope(id=shared, orgId="org-a")).status_code in {200, 409}


def test_primary_key_is_composite_in_the_model():
    assert [c.name for c in IntegrationEvent.__table__.primary_key.columns] == ["id", "organization_id"]


# ------------------------------------------------------------------------------------ timestamps

@pytest.mark.parametrize("offset", [-90000, 90000, -86400 * 365, 86400 * 365])
def test_event_time_must_be_close_to_now(client, offset):
    response = client.post(URL, json=envelope(time=now_iso(offset)))
    assert response.status_code == 422 and response.json()["detail"]["code"] == "event_time_out_of_range"


def test_event_time_within_the_skew_is_accepted_and_the_skew_is_configurable(client, monkeypatch):
    assert client.post(URL, json=envelope(time=now_iso(-3600))).status_code == 201
    assert client.post(URL, json=envelope(time=now_iso(3600))).status_code == 201
    install_settings(monkeypatch, integration_clock_skew_seconds=60)
    assert client.post(URL, json=envelope(time=now_iso(-3600))).status_code == 422
    assert client.post(URL, json=envelope(time=now_iso(-30))).status_code == 201


@pytest.mark.parametrize("stamp", ["9999-12-31T23:59:59-23:59", "0001-01-01T00:00:00+23:59", "99999-01-01T00:00:00Z", "2026-13-45T00:00:00Z",
                                   "2026-11-18T10:00:00+99:99", "0000-00-00T00:00:00Z"])
def test_extreme_timestamps_are_422_not_500(client, stamp):
    assert client.post(URL, json=envelope(time=stamp)).status_code == 422


# ------------------------------------------------------------------------------------ audited rejections and correlation

def test_security_rejections_are_audited_without_the_payload(client):
    body = envelope(data={"marker": "do-not-store-this"})
    client.post(URL, json=dict(body, orgId="org-b"))                              # 403 org mismatch
    client.post(URL, json=dict(body, id=str(uuid.uuid4()), source="jarvis"))     # 403 producer mismatch
    client.post(URL, json=envelope(data={"password": "do-not-store-this"}))      # 422 secret
    client.post(URL, json=envelope(severity="bogus"))                             # 422 validation
    first = envelope()
    client.post(URL, json=first)
    client.post(URL, json=dict(first, data={"files": 9}))                         # 409 conflict
    as_producer(client, "unknown-client")
    client.post(URL, json=envelope())                                             # 403 not authorized
    reasons = [(r.details["reason"], r.details["status"]) for r in rejections(client)]
    assert reasons == [("event_org_mismatch", 403), ("producer_mismatch", 403), ("event_data_contains_secret_like_content", 422),
                       ("invalid_event", 422), ("event_id_conflict", 409), ("producer_not_authorized", 403)]
    for row in rejections(client):
        assert row.outcome == "failure" and row.actor_id.startswith("svc-")
        assert "do-not-store-this" not in json.dumps(row.details) and "data" not in row.details
    assert rejections(client)[-1].details["client_id"] == "unknown-client"
    assert rejections(client)[0].entity_id == body["id"]


def test_accepted_events_are_not_recorded_as_rejections(client):
    assert client.post(URL, json=envelope()).status_code == 201
    assert rejections(client) == []


def test_x_request_id_is_accepted_as_the_correlation_header(client):
    first = envelope()
    assert client.post(URL, json=first, headers={"X-Request-ID": "req-12345678"}).status_code == 201
    second = envelope(correlationId="envelope-corr-1")
    assert client.post(URL, json=second, headers={"X-Correlation-ID": "hdr-corr-1234", "X-Request-ID": "req-87654321"}).status_code == 201
    third = envelope(correlationId="envelope-corr-3")
    assert client.post(URL, json=third).status_code == 201
    rows = db_of(client).scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.received").order_by(AuditEvent.created_at)).all()
    assert [r.correlation_id for r in rows] == ["req-12345678", "hdr-corr-1234", "envelope-corr-3"]


@pytest.mark.parametrize("header", ["short", "has space here", "x" * 65, "bad;chars!!", "new\nline12345"])
def test_malformed_correlation_headers_are_rejected_and_audited(client, header):
    for name in ("X-Correlation-ID", "X-Request-ID"):
        response = client.post(URL, json=envelope(), headers={name: header.replace("\n", "")} if "\n" not in header else {name: "bad;chars!!"})
        assert response.status_code == 422 and response.json()["detail"]["code"] == "invalid_correlation_id"
    assert client.get(URL).json() == []
    assert {r.details["reason"] for r in rejections(client)} == {"invalid_correlation_id"}


def test_rate_limited_requests_are_not_audited_so_a_flood_cannot_fill_the_audit_log(client, monkeypatch):
    install_settings(monkeypatch, integration_rate_per_minute=1, integration_rate_burst=1)
    client.post(URL, json=envelope())
    for _ in range(5):
        assert client.post(URL, json=envelope()).status_code == 429
    assert rejections(client) == []
