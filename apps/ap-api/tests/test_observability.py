import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import asaa_ap.main as main
from asaa_ap.main import app
from asaa_ap.observability import JsonFormatter, REDACTED, metrics, redact
from asaa_ap.security import Principal, get_principal


@pytest.fixture
def log_lines():
    lines = []

    class Capture(logging.Handler):
        def emit(self, record):
            lines.append(json.loads(JsonFormatter().format(record)))

    handler = Capture()
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield lines
    root.removeHandler(handler)
    root.setLevel(previous)


def test_health_is_dependency_free_and_ready_checks_database(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200 and ready.json() == {"status": "ready", "database": "available"}


def test_ready_returns_503_without_leaking_details_when_database_is_down(client, monkeypatch, log_lines):
    class Broken:
        def connect(self):
            raise OperationalError("SELECT 1", {}, Exception("password authentication failed for user asaa host=10.0.0.5"))

    monkeypatch.setattr(main, "engine", Broken())
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
    assert "password" not in response.text and "10.0.0.5" not in response.text
    assert any(line["message"] == "readiness_check_failed" and line["level"] == "ERROR" for line in log_lines)
    assert client.get("/health").status_code == 200  # liveness independent of the database


def test_request_id_is_generated_echoed_and_unsafe_values_are_replaced(client):
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 32
    assert client.get("/health", headers={"X-Request-ID": "trace-12345678"}).headers["x-request-id"] == "trace-12345678"
    hostile = client.get("/health", headers={"X-Request-ID": "x\"}{injected log\\n"}).headers["x-request-id"]
    assert hostile != "x\"}{injected log\\n" and len(hostile) == 32
    assert client.get("/health", headers={"X-Correlation-ID": "corr-abcdef12"}).headers["x-request-id"] == "corr-abcdef12"


def test_access_log_is_structured_has_request_id_and_excludes_query_secrets(client, log_lines):
    client.get("/api/v1/ap/suppliers?access_token=abc123&email=bob@example.com", headers={"X-Request-ID": "req-00000001", "Authorization": "Bearer eyJhbGciOi.eyJzdWIiOi.sig"})
    lines = [line for line in log_lines if line["message"] == "request"]
    assert lines and lines[-1]["request_id"] == "req-00000001"
    assert lines[-1]["method"] == "GET" and lines[-1]["status"] == 200 and lines[-1]["duration_ms"] >= 0
    blob = json.dumps(log_lines)
    for secret in ("abc123", "bob@example.com", "eyJhbGciOi", "Bearer "):
        assert secret not in blob


def test_unhandled_exception_is_logged_redacted_and_client_gets_generic_500(client, log_lines):
    from asaa_ap.database import get_db

    def exploding_db():
        raise RuntimeError("connect failed postgresql://asaa:SuperSecret1@db.internal/asaa token=abcdef")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = exploding_db
    safe = TestClient(app, raise_server_exceptions=False)
    response = safe.get("/api/v1/ap/suppliers")
    assert response.status_code == 500
    assert "SuperSecret1" not in response.text
    errors = [line for line in log_lines if line["message"] == "unhandled_exception"]
    assert errors and errors[0]["exception"]["type"] == "RuntimeError"
    assert "SuperSecret1" not in json.dumps(log_lines) and "abcdef" not in json.dumps(log_lines)


def test_redaction_masks_keys_and_value_patterns():
    data = {
        "authorization": "Bearer abc.def.ghi", "password": "hunter2", "gross_amount": "65000.00",
        "note": "contact alice@example.org with token=xyz",
        "nested": {"bank_account_number": "123456789", "ok": "visible", "list": ["a@b.co", "plain"]},
        "url": "postgresql+psycopg://user:pw123@host/db",
    }
    out = redact(data)
    assert out["authorization"] == REDACTED and out["password"] == REDACTED and out["gross_amount"] == REDACTED
    assert "alice@example.org" not in out["note"] and "xyz" not in out["note"]
    assert out["nested"]["bank_account_number"] == REDACTED and out["nested"]["ok"] == "visible"
    assert out["nested"]["list"] == [REDACTED, "plain"]
    assert "pw123" not in out["url"] and "user:" in out["url"]
    assert redact("-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----") == REDACTED


def test_structured_extra_fields_are_redacted_in_formatter():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "login from %s", ("a@b.com",), None)
    record.password = "pw"
    record.safe = "ok"
    entry = json.loads(JsonFormatter().format(record))
    assert entry["password"] == REDACTED and entry["safe"] == "ok" and "a@b.com" not in entry["message"]


def test_metrics_endpoint_counts_requests_by_route_template(client, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="development", metrics_token=None))
    metrics.reset()
    client.get("/api/v1/ap/suppliers/11111111-2222-3333-4444-555555555555")
    client.get("/api/v1/ap/suppliers/aaaaaaaa-2222-3333-4444-555555555555")
    body = client.get("/metrics").text
    assert "asaa_http_requests_total" in body and "asaa_http_request_duration_seconds_bucket" in body
    suppliers_lines = [l for l in body.splitlines() if l.startswith("asaa_http_requests_total") and "/suppliers" in l]
    assert suppliers_lines, body
    # ids must be collapsed: one series, count 2, never one series per id
    assert len(suppliers_lines) == 1 and suppliers_lines[0].endswith(" 2")
    assert "11111111-2222" not in body


def test_metrics_endpoint_is_protected_by_token_and_hidden_in_production(client, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="production", metrics_token=None))
    assert client.get("/metrics").status_code == 404
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="production", metrics_token="s3cret-token"))
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200


def test_authorization_failures_are_visible_in_metrics(client, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="development", metrics_token=None))
    metrics.reset()
    app.dependency_overrides[get_principal] = lambda: Principal("nobody", "org-a", frozenset())
    assert client.get("/api/v1/ap/suppliers").status_code == 403
    assert 'status="403"' in client.get("/metrics").text


def test_security_headers_and_no_store_on_api_responses(client):
    api = client.get("/api/v1/ap/suppliers")
    assert api.headers["x-content-type-options"] == "nosniff"
    assert api.headers["x-frame-options"] == "DENY"
    assert api.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in api.headers["content-security-policy"]
    assert client.get("/health").headers["referrer-policy"] == "no-referrer"


def test_oversized_request_bodies_are_rejected_with_413(client):
    response = client.post("/api/v1/ap/suppliers", content=b"x" * (1_048_576 + 10), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"


def test_api_docs_are_disabled_in_production_mode(monkeypatch):
    import importlib
    import asaa_ap.config as config
    monkeypatch.setenv("ASAA_AP_ENVIRONMENT", "production")
    monkeypatch.setenv("ASAA_AP_DATABASE_URL", "postgresql+psycopg://u@h/db")
    config.get_settings.cache_clear()
    try:
        prod_main = importlib.reload(main)
        assert prod_main.app.docs_url is None and prod_main.app.openapi_url is None
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()
        importlib.reload(main)
