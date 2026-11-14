from fastapi.testclient import TestClient
from asaa_ap.main import app
from asaa_ap.security import get_principal, Principal


def test_missing_permission_is_denied(client):
    app.dependency_overrides[get_principal] = lambda: Principal("reader", "org-a", frozenset({"supplier:read"}))
    response = client.post("/api/v1/ap/suppliers", json={"legal_name": "Restricted Supplier"})
    assert response.status_code == 403


def test_jwt_verification_enforces_configured_mfa_assurance(monkeypatch):
    from types import SimpleNamespace
    from datetime import datetime, timedelta, timezone
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import asaa_ap.security as security

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    settings = SimpleNamespace(
        jwt_public_key=public_key, jwt_jwks_url=None, jwt_issuer="https://issuer.example",
        jwt_audience="asaa-api", jwt_algorithm="RS256", jwt_leeway_seconds=0,
        required_acr="urn:asaa:loa:2", required_amr="otp",
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "person-1", "org_id": "org-1", "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=5),
        "acr": settings.required_acr, "amr": ["pwd", "otp"], "permissions": ["organization:profile:read"],
    }
    token = jwt.encode(claims, private_key, algorithm="RS256")
    principal = security.get_principal("Bearer " + token)
    assert principal.subject == "person-1"
    assert principal.organization_id == "org-1"

    claims["amr"] = ["pwd"]
    token_without_mfa = jwt.encode(claims, private_key, algorithm="RS256")
    try:
        security.get_principal("Bearer " + token_without_mfa)
        assert False, "Missing MFA method must be rejected"
    except Exception as error:
        from fastapi import HTTPException
        assert isinstance(error, HTTPException)
        assert error.status_code == 403
