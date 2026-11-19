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


class AuthenticationProviderError(TransientProviderError):
    """The adapter's own credentials were refused (token request, 401 or 403 from the admin API). It is an operator problem, not a
    property of the job: jobs are retried with a long backoff, an alert is raised and leaver jobs are never dead-lettered for it."""


class ProviderUserNotFound(ProviderError):
    """A leaver refers to an account the provider does not have. Adapters that cannot tell a missing account from a revoked one
    must not silently succeed: the job gets the distinct NotFound outcome and an alert."""


@dataclass(frozen=True)
class ProviderUser:
    subject: str
    active: bool
    entitlements: frozenset[str] = field(default_factory=frozenset)
    provider_id: str | None = None  # the provider's own immutable id, when it has one (for reconciliation)


@dataclass(frozen=True)
class UserAttributes:
    """Minimal attributes pushed to the provider. Contains personal data: never log or persist."""
    display_name: str | None = None
    email: str | None = None
    employee_reference: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    # True only for an explicit (re-)hire (joiner job): lets an adapter re-enable an account that was disabled outside ASAA.
    allow_reenable: bool = False


class IdentityProvider(ABC):
    @abstractmethod
    def upsert_user(self, subject: str, attributes: UserAttributes, active: bool) -> "str | None":
        """Create or update the user. May return the provider's own id for the user (audit and reconciliation)."""

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

    def adopt_account(self, subject: str, username: str, employee_reference: str | None, employee_email: str | None) -> str:
        """One-time, explicitly approved adoption of a pre-existing account for an employee. Returns the provider's id.
        Adapters that cannot prove the account belongs to the employee must refuse (PermanentProviderError)."""
        raise PermanentProviderError("This identity provider does not support adopting existing accounts")

    def drain_audit(self) -> list[dict]:
        """Provisioning steps taken since the last call (subject, provider id, action, group changes; no personal data)."""
        return []


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
