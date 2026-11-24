"""E3:D3.18 security review regressions: JWT validation matrix, CORS, mass assignment, HR document references, error leakage, audit immutability."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import asaa_ap.security as security
from asaa_ap.config import Settings
from asaa_ap.main import app

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
SETTINGS = SimpleNamespace(jwt_public_key=PUBLIC, jwt_jwks_url=None, jwt_issuer="https://issuer.example", jwt_audience="asaa-api", jwt_algorithm="RS256",
                           jwt_leeway_seconds=0, required_acr=None, required_amr=None)


def token(**override):
    now = datetime.now(timezone.utc)
    claims = {"sub": "p1", "org_id": "org-1", "iss": SETTINGS.jwt_issuer, "aud": SETTINGS.jwt_audience, "iat": now, "exp": now + timedelta(minutes=5), "permissions": ["x:read"], **override}
    return "Bearer " + jwt.encode({k: v for k, v in claims.items() if v is not None}, KEY, algorithm="RS256")


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: SETTINGS)


def status_of(header):
    with pytest.raises(HTTPException) as caught:
        security.get_principal(header)
    return caught.value.status_code


def test_valid_token_is_accepted():
    assert security.get_principal(token()).subject == "p1"


@pytest.mark.parametrize("override", [{"iss": "https://evil.example"}, {"aud": "other-api"}, {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                                      {"nbf": datetime.now(timezone.utc) + timedelta(minutes=10)}, {"sub": ""}, {"org_id": ""}, {"sub": 7}, {"org_id": None}])
def test_invalid_claims_are_refused_with_401(override):
    assert status_of(token(**override)) == 401


def test_algorithm_is_pinned_none_and_hs256_are_refused():
    forged_none = "Bearer " + jwt.encode({"sub": "p1", "org_id": "o", "iss": SETTINGS.jwt_issuer, "aud": SETTINGS.jwt_audience, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, key=None, algorithm="none")
    forged_hs = "Bearer " + jwt.encode({"sub": "p1", "org_id": "o", "iss": SETTINGS.jwt_issuer, "aud": SETTINGS.jwt_audience, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                                       "secret-secret-secret-secret-secret-1234", algorithm="HS256")
    assert status_of(forged_none) == 401 and status_of(forged_hs) == 401
    SETTINGS.jwt_algorithm = "HS256"
    try:
        assert status_of(token()) == 503
    finally:
        SETTINGS.jwt_algorithm = "RS256"


def test_jwks_must_be_https_off_loopback(monkeypatch):
    class Remote(SimpleNamespace):
        pass
    remote = Remote(**{**vars(SETTINGS), "jwt_public_key": None, "jwt_jwks_url": "http://idp.example.com/certs"})
    monkeypatch.setattr(security, "get_settings", lambda: remote)
    assert status_of(token()) == 503


def test_cors_wildcard_is_refused_in_production_and_staging():
    for environment in ("production", "staging"):
        with pytest.raises(ValueError):
            Settings(environment=environment, cors_origins=["*"], database_url="postgresql://u@h/db")
    assert Settings(cors_origins=["*"]).cors_origins == ["*"]  # development only


def test_every_request_body_model_rejects_unknown_fields():
    """Mass assignment: no route accepts fields the model does not declare."""
    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
            elif hasattr(route, "original_router"):
                yield from walk(route.original_router.routes)
    lax = {(r.body_field.field_info.annotation.__name__, r.path) for r in walk(app.routes)
           if r.body_field is not None and hasattr(r.body_field.field_info.annotation, "model_fields")
           and r.body_field.field_info.annotation.model_config.get("extra") != "forbid"}
    assert lax == set()


def test_no_file_upload_routes_and_audit_log_has_no_write_routes():
    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
            elif hasattr(route, "original_router"):
                yield from walk(route.original_router.routes)
    routes = list(walk(app.routes))
    assert not [r.path for r in routes if any("UploadFile" in repr(p.field_info.annotation) for p in r.dependant.body_params)]
    assert not [r.path for r in routes if "audit" in r.path and r.methods & {"POST", "PUT", "PATCH", "DELETE"}]


def test_unhandled_errors_do_not_leak_internals(client):
    @app.get("/__boom", include_in_schema=False)
    def boom():
        raise RuntimeError("secret connection string postgres://user:pw@host/db")
    try:
        with TestClient(app, raise_server_exceptions=False) as safe:
            response = safe.get("/__boom")
        assert response.status_code == 500
        assert "postgres" not in response.text and "pw@host" not in response.text and "Traceback" not in response.text
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/__boom"]


@pytest.mark.parametrize("reference", ["../../etc/passwd", "folder/../secret", "C:\\\\windows\\\\x", "https://user:pw@store.example/doc", "https://store.example/doc?sig=abc",
                                       "http://store.example/doc", "key\x00name"])
def test_hr_document_storage_reference_must_be_a_plain_key(client, reference):
    from tests.test_people import create_employee
    employee = create_employee(client)
    response = client.post(f"/api/v1/hr/employees/{employee['id']}/documents", json={"document_type": "Contract", "title": "Doc", "storage_reference": reference})
    assert response.status_code == 422


def test_hr_document_storage_reference_plain_key_is_accepted(client):
    from tests.test_people import create_employee
    employee = create_employee(client)
    for reference in ("hr/contracts/2026/doc-001.pdf", "s3://approved-bucket/hr/doc-001.pdf"):
        response = client.post(f"/api/v1/hr/employees/{employee['id']}/documents", json={"document_type": "Contract", "title": "Doc", "storage_reference": reference})
        assert response.status_code == 201, response.text


def test_hr_document_private_object_reference_is_accepted(client):
    from tests.test_people import create_employee
    employee = create_employee(client)
    for reference in ("private-object://hr/employee/document-001", "private-object://hr/contracts/2026/doc-002.pdf"):
        response = client.post(f"/api/v1/hr/employees/{employee['id']}/documents", json={"document_type": "Contract", "title": "Doc", "storage_reference": reference})
        assert response.status_code == 201, response.text


@pytest.mark.parametrize("reference", ["private-object://user:pw@hr/doc-001", "private-object://hr/doc-001?sig=abc", "private-object://hr/doc-001?token=x#frag",
                                       "private-object://tok@hr/doc-001"])
def test_hr_document_private_object_reference_rejects_credentials_and_query(client, reference):
    from tests.test_people import create_employee
    employee = create_employee(client)
    response = client.post(f"/api/v1/hr/employees/{employee['id']}/documents", json={"document_type": "Contract", "title": "Doc", "storage_reference": reference})
    assert response.status_code == 422
