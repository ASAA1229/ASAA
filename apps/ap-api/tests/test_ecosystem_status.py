"""Ecosystem status aggregation. The network transport is MOCKED here (a fake replaces asaa_integration.ecosystem.transport);
no real sibling service is contacted."""
import json
import time
from pathlib import Path

import pytest

from asaa_ap.security import Principal, get_principal
from asaa_integration import ecosystem

REGISTRY = Path(__file__).resolve().parents[3] / "contracts" / "ecosystem" / "v1" / "ecosystem-registry.json"
URL = "/api/v1/operations/ecosystem"


def as_p(client, perms=("ops:ecosystem:read",), org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal("ops", org, frozenset(perms))


def manifest(service, project, status="ok", **over):
    doc = {"schema": "asaa.service-manifest.v1", "service": service, "project": project, "version": "1.2.3", "commit": "abcdef1",
           "environment": "development", "status": status, "checkedAt": "2026-11-18T10:00:00.000Z",
           "checks": {"database": "ok"}, "capabilities": ["x.y"], "contracts": {"serviceManifest": "v1"}}
    doc.update(over)
    return doc


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    ecosystem.reset_cache()
    monkeypatch.setenv("ASAA_AP_ECOSYSTEM_REGISTRY_PATH", str(REGISTRY))
    monkeypatch.setattr(ecosystem, "get_settings", lambda: type("S", (), {
        "ecosystem_registry_path": str(REGISTRY), "ecosystem_allowed_hosts": [], "environment": "development", "build_commit": None})())
    yield
    ecosystem.reset_cache()


class FakeTransport:
    """Mock of the HTTP layer: maps URL -> (status, body) or an exception."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        result = self.routes.get(url)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise ConnectionRefusedError("refused")
        status, body = result
        return status, body if isinstance(body, bytes) else json.dumps(body).encode()


def by_service(body):
    return {row["service"]: row for row in body["services"]}


def test_aggregates_states_and_never_fails_when_siblings_are_offline(client, monkeypatch):
    as_p(client)
    fake = FakeTransport({
        "http://127.0.0.1:3000/.well-known/asaa-service": (200, manifest("jarvis", "JARVIS", "degraded")),
        "http://127.0.0.1:3100/v1/health": (200, {"status": "ok"}),
        "http://127.0.0.1:4000/.well-known/asaa-service": (503, b"unavailable"),
        # portfolio (8300) is simply offline
    })
    monkeypatch.setattr(ecosystem, "transport", fake)
    response = client.get(URL)
    assert response.status_code == 200
    rows = by_service(response.json())
    assert rows["asaa-api"]["status"] in {"ok", "degraded"} and rows["asaa-api"]["version"] == "0.4.0"
    assert rows["jarvis"] == {**rows["jarvis"], "status": "degraded", "version": "1.2.3", "commit": "abcdef1"}
    assert rows["jarvis-ai-gateway"]["status"] == "ok" and rows["jarvis-ai-gateway"]["version"] is None
    assert rows["templates-api"]["status"] == "down"
    assert rows["portfolio"]["status"] == "unreachable"
    assert set(rows) == {"asaa-api", "asaa-portal", "jarvis", "jarvis-ai-gateway", "templates-api", "templates-web", "portfolio"}
    # Services with neither manifestPath nor healthPath are listed but never probed.
    for portal in ("asaa-portal", "templates-web"):
        assert rows[portal]["status"] == "not-probed" and rows[portal]["version"] is None and rows[portal]["commit"] is None
    assert not any(any(port in url for port in (":5173", ":5000", ":8100", ":8200")) for url, _ in fake.calls)
    assert all("checkedAt" in row for row in rows.values())
    assert all(timeout <= 2 for _, timeout in fake.calls)
    assert not any(url.startswith("http://127.0.0.1:8001") for url, _ in fake.calls)  # self is not probed over HTTP


def test_everything_offline_still_returns_200(client, monkeypatch):
    as_p(client)
    monkeypatch.setattr(ecosystem, "transport", FakeTransport({}))
    response = client.get(URL)
    assert response.status_code == 200
    assert {r["status"] for r in response.json()["services"] if r["service"] != "asaa-api" and r["status"] != "not-probed"} == {"unreachable"}


def test_timeouts_and_garbage_are_mapped_not_raised(client, monkeypatch):
    as_p(client)
    monkeypatch.setattr(ecosystem, "transport", FakeTransport({
        "http://127.0.0.1:3000/.well-known/asaa-service": TimeoutError("slow"),
        "http://127.0.0.1:4000/.well-known/asaa-service": (200, b"<html>not json"),
        "http://127.0.0.1:8300/.well-known/asaa-service": (200, manifest("portfolio", "PORTFOLIO", extra="field")),
    }))
    rows = by_service(client.get(URL).json())
    assert rows["jarvis"]["status"] == "unreachable"
    assert rows["templates-api"]["status"] == "invalid"
    assert rows["portfolio"]["status"] == "invalid"


def test_manifest_identity_must_match_the_registry(client, monkeypatch):
    as_p(client)
    monkeypatch.setattr(ecosystem, "transport", FakeTransport({
        "http://127.0.0.1:3000/.well-known/asaa-service": (200, manifest("someone-else", "JARVIS")),
        "http://127.0.0.1:4000/.well-known/asaa-service": (200, manifest("templates-api", "JARVIS")),
    }))
    rows = by_service(client.get(URL).json())
    assert rows["jarvis"]["status"] == "invalid" and rows["templates-api"]["status"] == "invalid"


def test_results_are_cached_for_a_short_time(client, monkeypatch):
    as_p(client)
    fake = FakeTransport({})
    monkeypatch.setattr(ecosystem, "transport", fake)
    clock = [1000.0]
    monkeypatch.setattr(ecosystem, "_now", lambda: clock[0])
    client.get(URL)
    first = len(fake.calls)
    assert first > 0
    clock[0] += 10
    client.get(URL)
    assert len(fake.calls) == first
    clock[0] += 6
    client.get(URL)
    assert len(fake.calls) == 2 * first


def test_non_loopback_requires_an_explicit_allowlist(client, monkeypatch):
    as_p(client)
    fake = FakeTransport({"http://templates.internal.example:4000/.well-known/asaa-service": (200, manifest("templates-api", "TEMPLATES"))})
    monkeypatch.setattr(ecosystem, "transport", fake)
    monkeypatch.setenv("ASAA_AP_ECOSYSTEM_TEMPLATES_API_URL", "http://templates.internal.example:4000")
    blocked = by_service(client.get(URL).json())["templates-api"]
    assert blocked["status"] == "invalid" and "allowlist" in blocked["detail"]
    assert not any("internal.example" in url for url, _ in fake.calls)
    ecosystem.reset_cache()
    monkeypatch.setattr(ecosystem, "get_settings", lambda: type("S", (), {
        "ecosystem_registry_path": str(REGISTRY), "ecosystem_allowed_hosts": ["templates.internal.example"], "environment": "development"})())
    allowed = by_service(client.get(URL).json())["templates-api"]
    assert allowed["status"] == "ok"


@pytest.mark.parametrize("url,ok", [
    ("http://127.0.0.1:3000/x", True), ("http://localhost:3000/x", True), ("http://[::1]:3000/x", True), ("https://127.0.0.1/x", True),
    ("http://169.254.169.254/latest", False), ("http://10.0.0.5/x", False), ("http://example.com/x", False),
    ("file:///etc/passwd", False), ("ftp://127.0.0.1/x", False), ("http://user:pw@127.0.0.1/x", False), ("http:///x", False),
])
def test_url_policy(url, ok):
    assert ecosystem.url_allowed(url, []) is ok


def test_base_url_override_from_environment(monkeypatch):
    monkeypatch.setenv("ASAA_AP_ECOSYSTEM_JARVIS_AI_GATEWAY_URL", "http://127.0.0.1:9999")
    assert ecosystem.base_url_for({"service": "jarvis-ai-gateway", "devBaseUrl": "http://127.0.0.1:3100"}) == "http://127.0.0.1:9999"
    assert ecosystem.base_url_for({"service": "jarvis", "devBaseUrl": "http://127.0.0.1:3000"}) == "http://127.0.0.1:3000"


def test_missing_or_broken_registry_is_not_an_error(client, monkeypatch, tmp_path):
    as_p(client)
    bad = tmp_path / "registry.json"
    bad.write_text("{not json")
    for path in (tmp_path / "missing.json", bad):
        ecosystem.reset_cache()
        monkeypatch.setattr(ecosystem, "get_settings", lambda p=path: type("S", (), {
            "ecosystem_registry_path": str(p), "ecosystem_allowed_hosts": [], "environment": "development"})())
        response = client.get(URL)
        assert response.status_code == 200
        assert response.json()["services"] == [] and response.json()["registry"]["loaded"] is False


def test_permission_required(client):
    as_p(client, perms=())
    assert client.get(URL).status_code == 403
    as_p(client, perms=("ops:status:read",))
    assert client.get(URL).status_code == 403


def test_response_does_not_expose_urls_or_secrets(client, monkeypatch):
    as_p(client)
    monkeypatch.setattr(ecosystem, "transport", FakeTransport({}))
    text = client.get(URL).text
    assert "127.0.0.1" not in text and "http://" not in text


def test_slow_siblings_are_probed_concurrently(client, monkeypatch):
    as_p(client)

    def slow(url, timeout):
        time.sleep(0.4)
        raise TimeoutError

    monkeypatch.setattr(ecosystem, "transport", slow)
    started = time.monotonic()
    assert client.get(URL).status_code == 200
    assert time.monotonic() - started < 1.5  # 4 probed services in parallel, not 4 x 0.4 s in series


def test_validate_manifest_accepts_the_contract_example_and_rejects_bad_shapes():
    assert ecosystem.validate_manifest(manifest("asaa-api", "ASAA")) is None
    assert ecosystem.validate_manifest(manifest("asaa-api", "ASAA", commit=None)) is None
    for bad in (None, [], {}, manifest("A", "ASAA"), manifest("asaa-api", "NOPE"), manifest("asaa-api", "ASAA", status="up"),
                manifest("asaa-api", "ASAA", checks={"db": "maybe"}), manifest("asaa-api", "ASAA", capabilities=["a.b", "a.b"]),
                manifest("asaa-api", "ASAA", checkedAt="soon"), manifest("asaa-api", "ASAA", commit="XYZ")):
        assert ecosystem.validate_manifest(bad) is not None


def test_health_path_is_liveness_only_and_reports_no_version_or_commit(client, monkeypatch):
    as_p(client)
    url = "http://127.0.0.1:3100/v1/health"
    cases = [
        ((200, {"status": "ok", "version": "9.9.9", "commit": "abcdef1"}), "ok"),
        ((200, {"status": "degraded"}), "down"),
        ((200, {"healthy": True}), "down"),
        ((200, b"OK"), "down"),
        ((503, {"status": "ok"}), "down"),
        ((404, b""), "down"),
        (ConnectionRefusedError("refused"), "unreachable"),
        (TimeoutError("slow"), "unreachable"),
    ]
    for response, expected in cases:
        ecosystem.reset_cache()
        monkeypatch.setattr(ecosystem, "transport", FakeTransport({url: response}))
        row = by_service(client.get(URL).json())["jarvis-ai-gateway"]
        assert row["status"] == expected, (response, row)
        assert row["version"] is None and row["commit"] is None


def test_manifest_path_is_validated_while_health_path_is_not(client, monkeypatch):
    as_p(client)
    # The same JSON body is a valid health answer but an invalid manifest.
    body = {"status": "ok"}
    monkeypatch.setattr(ecosystem, "transport", FakeTransport({
        "http://127.0.0.1:3000/.well-known/asaa-service": (200, body),
        "http://127.0.0.1:3100/v1/health": (200, body),
    }))
    rows = by_service(client.get(URL).json())
    assert rows["jarvis"]["status"] == "invalid"
    assert rows["jarvis-ai-gateway"]["status"] == "ok"


def test_registry_contract_has_the_amended_gateway_entry():
    registry = json.loads(REGISTRY.read_text())
    gateway = next(s for p in registry["projects"] for s in p["services"] if s["service"] == "jarvis-ai-gateway")
    assert gateway["healthPath"] == "/v1/health" and "manifestPath" not in gateway
    assert all(("manifestPath" in s) + ("healthPath" in s) <= 1 for p in registry["projects"] for s in p["services"])


def test_service_with_neither_path_is_not_probed_even_with_a_url(client, monkeypatch, tmp_path):
    as_p(client)
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"schema": "asaa.ecosystem-registry.v1", "orgId": "asaa", "projects": [
        {"code": "PORTFOLIO", "services": [{"service": "portfolio-web", "devBaseUrl": "http://127.0.0.1:8300"}]}]}))
    monkeypatch.setattr(ecosystem, "get_settings", lambda: type("S", (), {
        "ecosystem_registry_path": str(reg), "ecosystem_allowed_hosts": [], "environment": "development"})())
    fake = FakeTransport({})
    monkeypatch.setattr(ecosystem, "transport", fake)
    rows = client.get(URL).json()["services"]
    assert [(r["service"], r["status"]) for r in rows] == [("portfolio-web", "not-probed")] and fake.calls == []
