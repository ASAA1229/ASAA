"""In-memory mock provider with fault injection. For tests and local development only."""
from __future__ import annotations

import threading
from collections import deque

from asaa_identity.provider import (IdentityProvider, PermanentProviderError, ProviderUser,
                                    TransientProviderError, UserAttributes)


class InMemoryIdentityProvider(IdentityProvider):
    def __init__(self):
        self._lock = threading.Lock()
        self.users: dict[str, dict] = {}
        self.calls: list[tuple] = []
        self._faults: deque = deque()

    # fault injection ---------------------------------------------------------
    def fail_next(self, count: int = 1, kind: str = "transient", operation: str | None = None):
        for _ in range(count):
            self._faults.append((kind, operation))

    def _maybe_fail(self, operation: str):
        if self._faults and self._faults[0][1] in (None, operation):
            kind, _ = self._faults.popleft()
            raise (TransientProviderError if kind == "transient" else PermanentProviderError)(f"injected {kind} failure in {operation}")

    # contract ------------------------------------------------------------------
    def upsert_user(self, subject, attributes: UserAttributes, active):
        with self._lock:
            self._maybe_fail("upsert_user")
            self.calls.append(("upsert_user", subject, active))
            record = self.users.setdefault(subject, {"active": active, "entitlements": set(), "sessions": 1})
            record["active"] = active
            record["attributes"] = attributes

    def disable_user(self, subject):
        with self._lock:
            self._maybe_fail("disable_user")
            self.calls.append(("disable_user", subject))
            if subject in self.users:
                self.users[subject]["active"] = False

    def set_entitlements(self, subject, entitlements):
        with self._lock:
            self._maybe_fail("set_entitlements")
            self.calls.append(("set_entitlements", subject, frozenset(entitlements)))
            if subject not in self.users:
                raise PermanentProviderError("user does not exist")
            self.users[subject]["entitlements"] = set(entitlements)

    def revoke_sessions(self, subject):
        with self._lock:
            self._maybe_fail("revoke_sessions")
            self.calls.append(("revoke_sessions", subject))
            if subject in self.users:
                self.users[subject]["sessions"] = 0

    def get_user(self, subject):
        with self._lock:
            record = self.users.get(subject)
            return ProviderUser(subject, record["active"], frozenset(record["entitlements"])) if record else None

    def list_users(self):
        with self._lock:
            return [ProviderUser(s, r["active"], frozenset(r["entitlements"])) for s, r in sorted(self.users.items())]

    # test helpers --------------------------------------------------------------
    def active_sessions(self, subject) -> int:
        return self.users.get(subject, {}).get("sessions", 0)
