"""OIDC + MFA verification against a LOCAL FAKE provider (never a real provider): JWKS over HTTP, key rotation, MFA claims, PKCE flow fidelity."""
import base64
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace

import jwt
import pytest

import asaa_ap.security as security
from asaa_ap.security import get_principal
from fake_oidc import FakeOidc


@pytest.fixture
def oidc():
    provider = FakeOidc().start()
    yield provider
    provider.stop()


@pytest.fixture
def configured(client, oidc, monkeypatch):
    """API configured to trust the fake provider through its JWKS endpoint, requiring MFA."""
    client.app.dependency_overrides.pop(get_principal)
    settings = SimpleNamespace(jwt_public_key=None, jwt_jwks_url=oidc.issuer + "/jwks", jwt_issuer=oidc.issuer, jwt_audience=oidc.audience, jwt_algorithm="RS256",
                               jwt_leeway_seconds=0, required_acr="urn:asaa:loa:2", required_amr="otp", jwks_refresh_cooldown_seconds=0)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    security.jwks_client.cache_clear()
    yield settings
    security.jwks_client.cache_clear()


def me(client, token):
    return client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})


def test_api_accepts_a_provider_token_verified_through_jwks_and_exposes_only_verified_claims(client, oidc, configured):
    response = me(client, oidc.access_token(permissions=["a:read", "b:write"]))
    assert response.status_code == 200
    assert response.json() == {"subject": "user-1", "organization_id": "org-a", "permissions": ["a:read", "b:write"]}


def test_mfa_assurance_is_enforced_from_acr_and_amr_claims(client, oidc, configured):
    assert me(client, oidc.access_token()).status_code == 200
    assert me(client, oidc.access_token(acr="urn:asaa:loa:1")).status_code == 403  # weaker authentication context
    assert me(client, oidc.access_token(amr=["pwd"])).status_code == 403  # password only, no second factor
    assert me(client, oidc.access_token(amr=None)).status_code == 403
    assert me(client, oidc.access_token(acr=None, amr=["otp"])).status_code == 403
    oidc.mfa = False
    assert me(client, oidc.access_token()).status_code == 403  # provider issued no MFA claims at all


def test_claim_validation_failures_are_rejected(client, oidc, configured):
    assert me(client, oidc.access_token(expires_in=-60)).status_code == 401
    assert me(client, oidc.access_token(aud="someone-else")).status_code == 401
    assert me(client, oidc.access_token(iss="http://evil.example")).status_code == 401
    assert me(client, oidc.access_token(org_id=None)).status_code == 401
    assert me(client, oidc.access_token(permissions="supplier:read")).status_code == 401


def test_signing_key_rotation_new_keys_are_picked_up_and_retired_keys_stop_working_after_refresh(client, oidc, configured):
    old_token = oidc.access_token()
    assert me(client, old_token).status_code == 200
    oidc.rotate(retire_old=False)  # overlap period: both keys published
    assert me(client, oidc.access_token()).status_code == 200  # unknown kid triggers a JWKS refresh
    assert me(client, old_token).status_code == 200  # old key still published
    oidc.rotate(retire_old=True)  # old keys withdrawn
    assert me(client, oidc.access_token()).status_code == 200
    security.jwks_client.cache_clear()  # simulate the JWKS cache lifespan elapsing
    assert me(client, old_token).status_code == 401


def test_rotation_is_picked_up_only_after_the_refresh_cooldown_which_bounds_provider_load(client, oidc, configured, monkeypatch):
    configured.jwks_refresh_cooldown_seconds = 3600  # a very long cooldown makes the protection observable
    security.jwks_client.cache_clear()
    assert me(client, oidc.access_token()).status_code == 200  # first fetch
    oidc.rotate(retire_old=False)
    assert me(client, oidc.access_token()).status_code == 401  # unknown kid inside the cooldown: no refetch
    configured.jwks_refresh_cooldown_seconds = 0
    security.jwks_client.cache_clear()
    assert me(client, oidc.access_token()).status_code == 200  # cooldown elapsed (or shorter): picked up


def test_token_signed_by_an_unpublished_key_or_with_none_algorithm_is_rejected(client, oidc, configured):
    rogue = FakeOidc(client_id="x")
    rogue.issuer = oidc.issuer  # same claims, different key
    forged = rogue.access_token()
    assert me(client, forged).status_code == 401
    assert me(client, jwt.encode({"sub": "u", "org_id": "org-a", "iss": oidc.issuer, "aud": oidc.audience, "exp": 4102444800}, None, algorithm="none")).status_code == 401
    rogue.server.server_close()


def test_provider_outage_fails_closed(client, oidc, configured):
    token = oidc.access_token()
    security.jwks_client.cache_clear()
    oidc.stop()
    assert me(client, token).status_code in (401, 503)


# ------------------------------------------------------------------ fidelity of the fake provider's authorization-code + PKCE flow
def pkce():
    verifier = base64.urlsafe_b64encode(b"v" * 40).rstrip(b"=").decode()
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def authorize(oidc, challenge, nonce="n-1", redirect="http://127.0.0.1:5173/cb"):
    query = urllib.parse.urlencode({"client_id": oidc.client_id, "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256",
                                    "redirect_uri": redirect, "state": "st", "nonce": nonce, "scope": "openid"})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(f"{oidc.issuer}/authorize?{query}")
    except urllib.error.HTTPError as redirect_response:
        location = redirect_response.headers["Location"]
        return urllib.parse.parse_qs(urllib.parse.urlparse(location).query), location
    raise AssertionError("expected a redirect")


def exchange(oidc, code, verifier, redirect="http://127.0.0.1:5173/cb"):
    body = urllib.parse.urlencode({"grant_type": "authorization_code", "code": code, "code_verifier": verifier, "client_id": oidc.client_id, "redirect_uri": redirect}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(oidc.issuer + "/token", data=body, method="POST")) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_authorization_code_flow_with_pkce_returns_verifiable_tokens_and_state(oidc):
    verifier, challenge = pkce()
    params, location = authorize(oidc, challenge, nonce="abc123")
    assert location.startswith("http://127.0.0.1:5173/cb?") and params["state"] == ["st"]
    status, tokens = exchange(oidc, params["code"][0], verifier)
    assert status == 200 and tokens["token_type"] == "Bearer"
    discovery = json.loads(urllib.request.urlopen(oidc.issuer + "/.well-known/openid-configuration").read())
    assert discovery["code_challenge_methods_supported"] == ["S256"] and discovery["jwks_uri"].endswith("/jwks")
    key = jwt.PyJWKClient(discovery["jwks_uri"]).get_signing_key_from_jwt(tokens["id_token"]).key
    claims = jwt.decode(tokens["id_token"], key, algorithms=["RS256"], audience=oidc.client_id, issuer=oidc.issuer)
    assert claims["nonce"] == "abc123" and claims["sub"] == "user-1"
    access = jwt.decode(tokens["access_token"], key, algorithms=["RS256"], audience=oidc.audience, issuer=oidc.issuer)
    assert access["amr"] == ["pwd", "otp"] and access["acr"] == "urn:asaa:loa:2"


def test_pkce_wrong_verifier_reused_code_and_wrong_redirect_are_refused(oidc):
    verifier, challenge = pkce()
    code = authorize(oidc, challenge)[0]["code"][0]
    assert exchange(oidc, code, "wrong-verifier")[0] == 400
    assert exchange(oidc, code, verifier)[0] == 400  # a failed attempt burns the code
    code2 = authorize(oidc, challenge)[0]["code"][0]
    assert exchange(oidc, code2, verifier, redirect="http://evil.example/cb")[0] == 400
    code3 = authorize(oidc, challenge)[0]["code"][0]
    assert exchange(oidc, code3, verifier)[0] == 200
    assert exchange(oidc, code3, verifier)[0] == 400  # single use
    with pytest.raises(urllib.error.HTTPError) as bad:
        urllib.request.urlopen(f"{oidc.issuer}/authorize?client_id={oidc.client_id}&response_type=code&redirect_uri=http://x/cb")  # no PKCE challenge
    assert bad.value.code == 400
