from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, OAuth2AuthorizationCodeBearer

from asaa_ap.config import get_settings


@lru_cache(maxsize=4)
def jwks_client(url: str, cooldown_seconds: float = 10):
    """JWKS client. An unknown key id forces a refresh at most once per cooldown, so a provider key rotation is picked up within
    that window while a flood of forged key ids cannot make the API hammer the provider."""
    try:
        return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300, cooldown_duration=cooldown_seconds)
    except TypeError:  # PyJWT releases before the refresh cooldown parameter
        return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300)


@dataclass(frozen=True)
class Principal:
    subject: str
    organization_id: str
    permissions: frozenset[str]
    client_id: str | None = None  # the token's azp (authorized party); identifies service-account producers


def build_bearer_scheme(settings=None):
    """The declared OpenAPI security scheme. auto_error=False keeps the 401/503 behaviour and messages of get_principal unchanged:
    the scheme only describes the bearer token (Swagger UI Authorize button); it never rejects a request itself."""
    settings = settings or get_settings()
    if settings.docs_oidc_authorization_url and settings.docs_oidc_token_url:
        return OAuth2AuthorizationCodeBearer(authorizationUrl=settings.docs_oidc_authorization_url, tokenUrl=settings.docs_oidc_token_url,
                                             scopes={"openid": "OpenID Connect sign-in"}, scheme_name="asaa_oidc", auto_error=False)
    return HTTPBearer(scheme_name="asaa_bearer", bearerFormat="JWT", description="Paste an RS256 access token issued by the configured identity provider.", auto_error=False)


bearer_scheme = build_bearer_scheme()


def authorization_header(request: Request, _declared=Security(bearer_scheme)) -> str | None:
    """The raw Authorization header; get_principal validates it exactly as before."""
    return request.headers.get("authorization")


def get_principal(authorization: Annotated[str | None, Depends(authorization_header)] = None) -> Principal:
    settings = get_settings()
    if not (settings.jwt_public_key or settings.jwt_jwks_url) or not settings.jwt_issuer or not settings.jwt_audience:
        raise HTTPException(status_code=503, detail="Identity verification is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    token = authorization[7:].strip()
    try:
        if settings.jwt_algorithm != "RS256":
            raise HTTPException(status_code=503, detail="Only RS256 identity tokens are supported")
        if settings.jwt_jwks_url:
            parsed = urlparse(settings.jwt_jwks_url)
            if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
                raise HTTPException(status_code=503, detail="Identity JWKS URL must use HTTPS")
            signing_key = jwks_client(settings.jwt_jwks_url, getattr(settings, "jwks_refresh_cooldown_seconds", 10)).get_signing_key_from_jwt(token).key
        else:
            signing_key = settings.jwt_public_key
        if not signing_key:
            raise HTTPException(status_code=503, detail="Identity signing key is not configured")
        claims = jwt.decode(
            token, signing_key, algorithms=["RS256"], issuer=settings.jwt_issuer,
            audience=settings.jwt_audience, leeway=settings.jwt_leeway_seconds,
            options={"require": ["sub", "org_id", "iss", "aud", "exp"]},
        )
        if settings.required_acr and claims.get("acr") != settings.required_acr:
            raise HTTPException(status_code=403, detail="Required authentication assurance level not met")
        if settings.required_amr:
            amr = claims.get("amr", [])
            if not isinstance(amr, list) or settings.required_amr not in amr:
                raise HTTPException(status_code=403, detail="Required multi-factor authentication method not present")
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}) from None
    permissions = claims.get("permissions", [])
    if not isinstance(permissions, list) or not all(isinstance(p, str) for p in permissions):
        raise HTTPException(status_code=401, detail="Invalid permission claims")
    azp = claims.get("azp")
    return Principal(str(claims["sub"]), str(claims["org_id"]), frozenset(permissions), azp if isinstance(azp, str) and azp else None)


def require_permission(permission: str):
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if permission not in principal.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        # A registered event-producer service account (token azp) may only use the integration event routes, whatever its token claims.
        if principal.client_id and principal.client_id in get_settings().integration_producers and not permission.startswith("integration:event:"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service account is not permitted on this route")
        return principal
    return dependency
