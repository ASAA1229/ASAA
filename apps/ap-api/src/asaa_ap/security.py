from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from asaa_ap.config import get_settings


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
        claims = jwt.decode(
            token,
            settings.jwt_public_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "org_id", "iss", "aud", "exp"]},
        )
    except jwt.PyJWTError:
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
