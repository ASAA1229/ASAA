"""GET /.well-known/asaa-service conforms to contracts/ecosystem/v1/service-manifest.schema.json and leaks nothing."""
import json
from pathlib import Path

import jsonschema
import pytest

from asaa_integration import manifest as manifest_module

@pytest.fixture(autouse=True)
def fresh_check_cache():
    manifest_module.reset_cache()
    yield
    manifest_module.reset_cache()


SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "contracts" / "ecosystem" / "v1" / "service-manifest.schema.json").read_text())


def test_manifest_is_unauthenticated_and_schema_valid(client):
    client.app.dependency_overrides.clear()  # no principal override: the route must not need a token
    response = client.get("/.well-known/asaa-service")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker()).validate(body)
    assert body["service"] == "asaa-api" and body["project"] == "ASAA"
    assert set(body["checks"]) == {"database", "migrations"}
    assert body["capabilities"] == ["organization", "governance", "events.ingest", "ecosystem.status"]
    assert body["checks"]["database"] == "ok"


def test_manifest_contains_no_secret_material(client, monkeypatch):
    monkeypatch.setenv("ASAA_AP_JWT_PUBLIC_KEY", "should-not-appear")
    text = client.get("/.well-known/asaa-service").text.lower()
    for forbidden in ("postgresql", "sqlite", "password", "secret", "token", "private", "should-not-appear"):
        assert forbidden not in text


def test_manifest_commit_only_accepts_hex_sha(client, monkeypatch):
    class S:
        environment = "test"
        build_commit = "4419B25"
    monkeypatch.setattr(manifest_module, "get_settings", lambda: S)
    assert client.get("/.well-known/asaa-service").json()["commit"] == "4419b25"
    S.build_commit = "not a sha; drop table"
    assert client.get("/.well-known/asaa-service").json()["commit"] is None


def test_manifest_reports_database_down_without_failing(client, monkeypatch):
    monkeypatch.setattr(manifest_module, "check_database", lambda: "down")
    response = client.get("/.well-known/asaa-service")
    body = response.json()
    assert response.status_code == 200 and body["status"] == "down" and body["checks"] == {"database": "down", "migrations": "down"}
    jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker()).validate(body)


def test_dependency_checks_are_cached_so_the_public_endpoint_cannot_hammer_the_database(client, monkeypatch):
    calls = []
    clock = [100.0]
    monkeypatch.setattr(manifest_module, "_now", lambda: clock[0])
    monkeypatch.setattr(manifest_module, "check_database", lambda: calls.append("db") or "ok")
    monkeypatch.setattr(manifest_module, "check_migrations", lambda: calls.append("mig") or "ok")
    for _ in range(20):
        assert client.get("/.well-known/asaa-service").json()["checks"] == {"database": "ok", "migrations": "ok"}
    assert calls == ["db", "mig"]
    clock[0] += manifest_module.CHECK_CACHE_SECONDS + 1
    client.get("/.well-known/asaa-service")
    assert calls == ["db", "mig", "db", "mig"]
