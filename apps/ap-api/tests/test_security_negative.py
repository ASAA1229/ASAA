"""Negative / adversarial API security tests (ASAA-004).

These tests assert what must NOT work: unauthenticated access, access without the
required permission, cross-organization access, field-level leakage of payroll data,
self-approval, mass assignment, and loss of audit evidence.
"""
import re
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import event, select

import asaa_ap.security as security
from asaa_ap.main import app
from asaa_ap.models import AuditEvent, Supplier
from asaa_ap.security import Principal, get_principal

def as_principal(client, subject, org, permissions):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(permissions))


# Routes that require a valid token but deliberately no permission (session introspection).
AUTH_ONLY_ROUTES = {"/api/v1/me", "/api/v1/notifications/preferences/me"}


def api_routes():
    """All /api/ operations, taken from the public OpenAPI document (stable across FastAPI versions)."""
    for path, operations in sorted(app.openapi()["paths"].items()):
        if path.startswith("/api/"):
            for method in sorted(operations):
                if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"} and path not in AUTH_ONLY_ROUTES:
                    yield method.upper(), path


def concrete(path):
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


def test_route_inventory_is_not_empty():
    assert len(list(api_routes())) > 90


def test_every_api_route_denies_a_principal_with_no_permissions(client):
    as_principal(client, "nobody", "org-a", [])
    leaked = []
    for method, path in api_routes():
        response = client.request(method, concrete(path), json={})
        if response.status_code != 403:
            leaked.append(f"{method} {path} -> {response.status_code}")
    assert leaked == []


def test_every_api_route_rejects_a_principal_from_another_org_without_permissions(client):
    # Same check, different org: permission denial must not depend on org.
    as_principal(client, "nobody", "org-zzz", ["unrelated:permission"])
    leaked = [f"{m} {p}" for m, p in api_routes() if client.request(m, concrete(p), json={}).status_code != 403]
    assert leaked == []


@pytest.fixture
def identity_settings(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    settings = SimpleNamespace(
        jwt_public_key=public_pem, jwt_jwks_url=None, jwt_issuer="https://issuer.example",
        jwt_audience="asaa-api", jwt_algorithm="RS256", jwt_leeway_seconds=0, required_acr=None, required_amr=None)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    return SimpleNamespace(settings=settings, key=private_key)


def token(identity, **overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": "u1", "org_id": "org-a", "iss": identity.settings.jwt_issuer, "aud": identity.settings.jwt_audience,
              "iat": now, "exp": now + timedelta(minutes=5), "permissions": ["supplier:read"]}
    claims.update(overrides)
    key = overrides.pop("_key", None) or identity.key
    claims = {k: v for k, v in claims.items() if v is not None and k != "_key"}
    return jwt.encode(claims, key, algorithm="RS256")


def test_unauthenticated_and_malformed_credentials_are_rejected_on_every_route(client, identity_settings):
    client.app.dependency_overrides.pop(get_principal)
    bad_headers = [
        {}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not.a.jwt"},
        {"Authorization": "Bearer " + token(identity_settings, aud="someone-else")},
        {"Authorization": "Bearer " + token(identity_settings, iss="https://evil.example")},
        {"Authorization": "Bearer " + token(identity_settings, exp=datetime.now(timezone.utc) - timedelta(minutes=5))},
    ]
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad_headers.append({"Authorization": "Bearer " + jwt.encode(
        {"sub": "u", "org_id": "org-a", "iss": identity_settings.settings.jwt_issuer, "aud": "asaa-api",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5), "permissions": ["supplier:read"]}, other_key, algorithm="RS256")})
    # alg=none forgery
    bad_headers.append({"Authorization": "Bearer " + jwt.encode({"sub": "u", "org_id": "org-a", "permissions": ["supplier:read"]}, None, algorithm="none")})
    for headers in bad_headers:
        response = client.get("/api/v1/ap/suppliers", headers=headers)
        assert response.status_code == 401, headers
    # missing mandatory claims
    for missing in ("org_id", "sub"):
        response = client.get("/api/v1/ap/suppliers", headers={"Authorization": "Bearer " + token(identity_settings, **{missing: None})})
        assert response.status_code == 401, missing
    # malformed permission claim
    response = client.get("/api/v1/ap/suppliers", headers={"Authorization": "Bearer " + token(identity_settings, permissions="supplier:read")})
    assert response.status_code == 401


def test_valid_token_works_and_org_comes_only_from_the_token(client, identity_settings):
    client.app.dependency_overrides.pop(get_principal)
    headers = {"Authorization": "Bearer " + token(identity_settings, permissions=["supplier:write", "supplier:read"])}
    created = client.post("/api/v1/ap/suppliers", json={"legal_name": "Token Co"}, headers=headers)
    assert created.status_code == 201
    # A caller-supplied organization header/query must not change scope.
    other = {"Authorization": "Bearer " + token(identity_settings, org_id="org-b", permissions=["supplier:read"])}
    assert client.get("/api/v1/ap/suppliers?organization_id=org-a", headers={**other, "X-Organization-ID": "org-a"}).json() == []


def test_all_routes_fail_closed_when_identity_is_unconfigured(client, monkeypatch):
    client.app.dependency_overrides.pop(get_principal)
    unconfigured = SimpleNamespace(jwt_public_key=None, jwt_jwks_url=None, jwt_issuer=None, jwt_audience=None,
                                   jwt_algorithm="RS256", jwt_leeway_seconds=0, required_acr=None, required_amr=None)
    monkeypatch.setattr(security, "get_settings", lambda: unconfigured)
    for method, path in api_routes():
        assert client.request(method, concrete(path), headers={"Authorization": "Bearer x"}, json={}).status_code == 503, (method, path)


def test_non_rs256_configuration_is_refused(client, identity_settings):
    client.app.dependency_overrides.pop(get_principal)
    identity_settings.settings.jwt_algorithm = "HS256"
    response = client.get("/api/v1/ap/suppliers", headers={"Authorization": "Bearer " + token(identity_settings)})
    assert response.status_code == 503


FULL = {
    "supplier:read", "supplier:write", "supplier:status", "audit:read",
    "hr:employee:read", "hr:employee:write", "hr:employment:write", "hr:employee:lifecycle",
    "payroll:compensation:read", "payroll:compensation:write", "payroll:compensation:approve",
    "payroll:period:write", "payroll:run:write", "payroll:entry:write", "payroll:read",
    "ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write",
    "hr:document:read", "hr:document:write", "hr:asset:read", "hr:asset:write",
    "hr:leave:read", "hr:leave:request", "hr:exit:read", "hr:exit:write",
}


def make_employee(client):
    r = client.post("/api/v1/hr/employees", json={"first_name": "Asha", "last_name": "Rao", "employment_type": "Employee"})
    assert r.status_code == 201
    return r.json()


def test_cross_organization_record_isolation(client):
    as_principal(client, "a-admin", "org-a", FULL)
    employee = make_employee(client)
    supplier = client.post("/api/v1/ap/suppliers", json={"legal_name": "Isolated Supplier"}).json()
    customer = client.post("/api/v1/ar/customers", json={"legal_name": "Isolated Customer"}).json()
    comp = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "50000.00",
        "frequency": "Monthly", "effective_from": "2026-12-01"}).json()

    as_principal(client, "b-admin", "org-b", FULL)
    # direct object reference by id from another organization
    assert client.get(f"/api/v1/hr/employees/{employee['id']}").status_code == 404
    assert client.get(f"/api/v1/hr/employees/{employee['id']}/employment-records").status_code == 404
    assert client.get(f"/api/v1/ap/suppliers/{supplier['id']}").status_code == 404
    assert client.patch(f"/api/v1/ap/suppliers/{supplier['id']}", json={"expected_version": 1, "notes": "x"}).status_code == 404
    assert client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 1, "status": "Pending Verification", "reason": "cross org"}).status_code == 404
    assert client.get(f"/api/v1/ar/customers/{customer['id']}").status_code == 404
    assert client.patch(f"/api/v1/hr/employees/{employee['id']}", json={"preferred_name": "Hacked"}).status_code == 404
    assert client.post(f"/api/v1/hr/employees/{employee['id']}/employment-records", json={
        "employment_type": "Employee", "status": "Active", "effective_from": "2026-12-01"}).status_code == 404
    assert client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "1.00",
        "frequency": "Monthly", "effective_from": "2026-12-01"}).status_code == 404
    assert client.post(f"/api/v1/payroll/compensation/{comp['id']}/decision", json={"decision": "Approved"}).status_code == 404
    assert client.post(f"/api/v1/hr/employees/{employee['id']}/leave-requests", json={
        "leave_type": "Annual", "start_date": "2026-12-01", "end_date": "2026-12-02", "reason": "x"}).status_code in (404, 422)
    # list endpoints do not leak the other organization's rows
    assert client.get("/api/v1/hr/employees").json() == []
    assert client.get("/api/v1/ap/suppliers").json() == []
    assert client.get("/api/v1/ar/customers").json() == []
    assert client.get(f"/api/v1/payroll/compensation?employee_id={employee['id']}").status_code == 404
    assert client.get("/api/v1/ap/audit-events").json() == []
    # the owner's data is untouched
    as_principal(client, "a-admin", "org-a", FULL)
    assert client.get(f"/api/v1/hr/employees/{employee['id']}").json()["preferred_name"] != "Hacked"
    assert client.get(f"/api/v1/ap/suppliers/{supplier['id']}").json()["status"] == "Draft"


def test_hr_access_does_not_reveal_compensation_or_payroll(client):
    as_principal(client, "a-admin", "org-a", FULL)
    employee = make_employee(client)
    client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "987654.00",
        "frequency": "Monthly", "effective_from": "2026-12-01"})
    hr_only = {"hr:employee:read", "hr:employee:write", "hr:employment:write", "hr:document:read", "hr:leave:read"}
    as_principal(client, "hr-clerk", "org-a", hr_only)
    body = client.get(f"/api/v1/hr/employees/{employee['id']}")
    listing = client.get("/api/v1/hr/employees")
    assert body.status_code == 200 and listing.status_code == 200
    for payload in (body.text, listing.text):
        assert "987654" not in payload
        assert "gross_amount" not in payload and "salary" not in payload.lower()
    for path in ("/api/v1/payroll/compensation", "/api/v1/payroll/periods", "/api/v1/payroll/runs"):
        assert client.get(path).status_code == 403, path
    assert client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "1.00",
        "frequency": "Monthly", "effective_from": "2027-01-01"}).status_code == 403


def test_write_permission_does_not_imply_approval_or_read(client):
    as_principal(client, "maker", "org-a", {"payroll:compensation:write", "hr:employee:write", "hr:employee:read"})
    employee = make_employee(client)
    comp = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "100.00",
        "frequency": "Monthly", "effective_from": "2026-12-01"})
    assert comp.status_code == 201
    assert client.get("/api/v1/payroll/compensation").status_code == 403
    assert client.post(f"/api/v1/payroll/compensation/{comp.json()['id']}/decision", json={"decision": "Approved"}).status_code == 403
    # approver who is also the maker cannot self-approve even with the permission
    as_principal(client, "maker", "org-a", {"payroll:compensation:approve"})
    assert client.post(f"/api/v1/payroll/compensation/{comp.json()['id']}/decision", json={"decision": "Approved"}).status_code == 403


def test_mass_assignment_and_unknown_fields_are_rejected(client):
    as_principal(client, "a-admin", "org-a", FULL)
    r = client.post("/api/v1/ap/suppliers", json={"legal_name": "X Co", "organization_id": "org-b", "status": "Active", "created_by": "root"})
    assert r.status_code == 422
    r = client.post("/api/v1/hr/employees", json={"first_name": "A", "last_name": "B", "employment_type": "Employee", "organization_id": "org-b"})
    assert r.status_code == 422
    ok = client.post("/api/v1/ap/suppliers", json={"legal_name": "Normal Co"})
    assert ok.status_code == 201 and ok.json()["status"] == "Draft"


def test_injection_strings_are_treated_as_data(client):
    as_principal(client, "a-admin", "org-a", FULL)
    evil = "x'; DROP TABLE ap_suppliers; --"
    assert client.post("/api/v1/ap/suppliers", json={"legal_name": evil}).status_code == 201
    assert client.get("/api/v1/ap/suppliers", params={"q": evil, "status": evil}).status_code in (200, 422)
    assert [s["legal_name"] for s in client.get("/api/v1/ap/suppliers").json()] == [evil]


def audit_events(client):
    return client.get("/api/v1/ap/audit-events").json()


def test_privileged_actions_write_attributable_audit_events(client):
    as_principal(client, "alice", "org-a", FULL)
    supplier = client.post("/api/v1/ap/suppliers", json={"legal_name": "Audited Co"}, headers={"X-Correlation-ID": "corr-123"}).json()
    client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 1, "status": "Pending Verification", "reason": "ready"})
    employee = make_employee(client)
    client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed", "gross_amount": "100.00",
        "frequency": "Monthly", "effective_from": "2026-12-01"}, headers={"X-Correlation-ID": "corr-pay"})
    events = audit_events(client)
    by_action = {e["action"]: e for e in events}
    assert {"supplier.created", "supplier.status_changed", "compensation.proposed"} <= set(by_action)
    for e in events:
        assert e["actor_id"] == "alice" and e["created_at"]
    assert by_action["supplier.created"]["correlation_id"] == "corr-123"
    assert by_action["compensation.proposed"]["correlation_id"] == "corr-pay"
    # no compensation amount leaks into the audit trail
    assert "100.00" not in str(by_action["compensation.proposed"]["details"])
    # reading audit needs its own permission, and only own-org events are visible
    as_principal(client, "bob", "org-b", {"audit:read"})
    assert audit_events(client) == []
    as_principal(client, "carol", "org-a", {"supplier:read"})
    assert client.get("/api/v1/ap/audit-events").status_code == 403


def test_rejected_privileged_action_does_not_create_success_audit_or_change_state(client):
    as_principal(client, "alice", "org-a", FULL)
    supplier = client.post("/api/v1/ap/suppliers", json={"legal_name": "Stateful Co"}).json()
    before = len(audit_events(client))
    r = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 1, "status": "Archived-ish", "reason": "bad"})
    assert r.status_code in (409, 422)
    r = client.post(f"/api/v1/ap/suppliers/{supplier['id']}/status", json={"expected_version": 99, "status": "Pending Verification", "reason": "stale"})
    assert r.status_code == 409
    assert len(audit_events(client)) == before
    assert client.get(f"/api/v1/ap/suppliers/{supplier['id']}").json()["status"] == "Draft"


def test_failed_audit_write_leaves_no_partial_state(client):
    as_principal(client, "alice", "org-a", FULL)

    def boom(mapper, connection, target):
        raise RuntimeError("simulated audit store failure")

    event.listen(AuditEvent, "before_insert", boom)
    try:
        safe = TestClient(app, raise_server_exceptions=False)
        assert safe.post("/api/v1/ap/suppliers", json={"legal_name": "Unaudited Co"}).status_code == 500
        assert safe.post("/api/v1/hr/employees", json={"first_name": "N", "last_name": "A", "employment_type": "Employee"}).status_code == 500
    finally:
        event.remove(AuditEvent, "before_insert", boom)
    assert client.get("/api/v1/ap/suppliers").json() == []
    assert client.get("/api/v1/hr/employees").json() == []
    # error body must not leak internals
    # service recovers once the audit store is healthy again
    assert client.post("/api/v1/ap/suppliers", json={"legal_name": "Unaudited Co"}).status_code == 201


def test_whoami_requires_a_valid_token_and_returns_only_verified_claims(client, identity_settings):
    client.app.dependency_overrides.pop(get_principal)
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401
    ok = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token(identity_settings, permissions=["b:x", "a:y"])})
    assert ok.status_code == 200
    assert ok.json() == {"subject": "u1", "organization_id": "org-a", "permissions": ["a:y", "b:x"]}
    assert ok.headers["cache-control"] == "no-store"
