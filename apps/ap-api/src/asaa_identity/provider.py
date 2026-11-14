"""Identity provider adapter contract.

A concrete adapter (Entra ID, Okta, Keycloak, SCIM ...) implements IdentityProvider and is
registered with register_provider(). No real provider is configured or implied by this module.
All methods must be idempotent: calling them twice with the same arguments has the same effect.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


class ProviderError(Exception):
    """Base class for adapter failures."""


class TransientProviderError(ProviderError):
    """Timeout, 429/5xx, network failure: safe to retry later."""


class PermanentProviderError(ProviderError):
    """Validation/authorization/conflict failure that retrying will not fix: dead-letter for a human."""


@dataclass(frozen=True)
class ProviderUser:
    subject: str
    active: bool
    entitlements: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class UserAttributes:
    """Minimal attributes pushed to the provider. Contains personal data: never log or persist."""
    display_name: str | None = None
    email: str | None = None
    employee_reference: str | None = None


class IdentityProvider(ABC):
    @abstractmethod
    def upsert_user(self, subject: str, attributes: UserAttributes, active: bool) -> None: ...

    @abstractmethod
    def disable_user(self, subject: str) -> None:
        """Disable sign-in. Must succeed (no-op) if the user does not exist."""

    @abstractmethod
    def set_entitlements(self, subject: str, entitlements: frozenset[str]) -> None:
        """Replace the user's entitlements with exactly this set."""

    @abstractmethod
    def revoke_sessions(self, subject: str) -> None:
        """Invalidate refresh tokens/sessions. Must succeed (no-op) if the user does not exist."""

    @abstractmethod
    def get_user(self, subject: str) -> ProviderUser | None: ...

    @abstractmethod
    def list_users(self) -> list[ProviderUser]: ...


_FACTORIES: dict[str, Callable[[], IdentityProvider]] = {}
_INSTANCES: dict[str, IdentityProvider] = {}


def register_provider(name: str, factory: Callable[[], IdentityProvider]) -> None:
    _FACTORIES[name] = factory
    _INSTANCES.pop(name, None)


def resolve_provider(name: str) -> IdentityProvider | None:
    if name not in _FACTORIES:
        return None
    if name not in _INSTANCES:
        _INSTANCES[name] = _FACTORIES[name]()
    return _INSTANCES[name]
