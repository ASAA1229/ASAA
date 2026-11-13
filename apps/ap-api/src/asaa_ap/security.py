from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from asaa_ap.config import get_settings


@lru_cache(maxsize=4)
def jwks_client(url: str):
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300)


@dataclass(frozen=True)
class Principal:
    subject: str
    organization_id: str
    permissions: frozenset[str]


def get_principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
    settings = get_settings()
    if not settings.jwt_public_key or not settings.jwt_issuer or not settings.jwt_audience:
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
            signing_key = jwks_client(settings.jwt_jwks_url).get_signing_key_from_jwt(token).key
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
    return Principal(str(claims["sub"]), str(claims["org_id"]), frozenset(permissions))


def require_permission(permission: str):
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if permission not in principal.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return principal
    return dependency
