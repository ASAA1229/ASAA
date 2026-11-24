"""E3:D3.16 Swagger sign-in: the bearer scheme is declared in OpenAPI while the 401/503 behaviour of get_principal stays identical."""
import pytest
from fastapi.security import HTTPBearer, OAuth2AuthorizationCodeBearer

from asaa_ap import security
from asaa_ap.config import Settings
from asaa_ap.hardening import docs_csp
from asaa_ap.main import app
from fastapi.testclient import TestClient


def test_openapi_declares_a_bearer_security_scheme():
    document = app.openapi()
    schemes = document["components"]["securitySchemes"]
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes.values())
    assert document["paths"]["/api/v1/ar/customers"]["get"]["security"]


def test_unauthenticated_calls_still_return_401_and_missing_config_503(monkeypatch):
    app.dependency_overrides.clear()
    with TestClient(app) as anonymous:
        response = anonymous.get("/api/v1/ar/customers")
        assert response.status_code in {401, 503}
        if response.status_code == 503:
            assert response.json()["detail"] == "Identity verification is not configured"
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_public_key="k", jwt_issuer="i", jwt_audience="a"))
    with TestClient(app) as anonymous:
        response = anonymous.get("/api/v1/ar/customers")
        assert response.status_code == 401 and response.json()["detail"] == "Bearer token required"
        assert response.headers["www-authenticate"] == "Bearer"
        assert anonymous.get("/api/v1/ar/customers", headers={"Authorization": "Basic abc"}).json()["detail"] == "Bearer token required"


def test_oidc_settings_select_the_authorization_code_scheme_and_stay_public():
    plain = Settings()
    assert isinstance(security.build_bearer_scheme(plain), HTTPBearer)
    configured = Settings(docs_oidc_authorization_url="http://127.0.0.1:8280/realms/asaa/protocol/openid-connect/auth",
                          docs_oidc_token_url="http://127.0.0.1:8280/realms/asaa/protocol/openid-connect/token", docs_oidc_client_id="asaa-api-docs")
    scheme = security.build_bearer_scheme(configured)
    assert isinstance(scheme, OAuth2AuthorizationCodeBearer) and scheme.auto_error is False
    assert "secret" not in repr(configured.model_dump()).lower().replace("keycloak_client_secret", "")


def test_docs_oidc_urls_must_be_https_off_loopback():
    with pytest.raises(ValueError):
        Settings(docs_oidc_authorization_url="http://idp.example.com/auth", docs_oidc_token_url="https://idp.example.com/token")


def test_docs_csp_allows_only_the_token_origin(monkeypatch):
    monkeypatch.setattr("asaa_ap.config.get_settings", lambda: Settings(docs_oidc_authorization_url="http://127.0.0.1:8280/a", docs_oidc_token_url="http://127.0.0.1:8280/t"))
    assert b"connect-src 'self' http://127.0.0.1:8280;" in docs_csp()


def test_docs_are_disabled_in_production():
    prod = Settings(environment="production", database_url="postgresql://u@h/db")
    assert prod.environment == "production"  # main.py passes docs_url=None / swagger_ui_init_oauth=None when production
    import inspect, asaa_ap.main as main
    source = inspect.getsource(main)
    assert 'docs_url=None if _production' in source and "and not _production" in source
