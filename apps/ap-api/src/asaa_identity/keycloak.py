"""Keycloak identity provider adapter (Admin REST API, service-account client credentials).

ASAA HR lifecycle drives the single-sign-on accounts:
  joiner     create the user (username, email, first/last name from HR, enabled, required actions UPDATE_PASSWORD and
             CONFIGURE_TOTP) and add it to the base group. ASAA NEVER sets or sends a password or any credential.
  mover      update attributes and replace the managed groups.
  leaver     disable the user and log out all sessions (POST /users/{id}/logout).
Entitlement "x" maps to the group "<group_prefix>x" (default "asaa:", same convention as the SCIM adapter); only groups with
that prefix are managed, so the base group and unrelated groups are never touched.

Reliability follows the identity worker contract: network failures, 429 and 5xx retry with backoff and then raise
TransientProviderError (the outbox retries later); 401 re-authenticates once, then 4xx raise PermanentProviderError.
Lookups by username before create make every method idempotent; a 409 on create falls back to update.
The client secret and access token are only ever placed in the token request and the Authorization header; they are never
logged and never appear in exception messages.
"""
from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Callable

from asaa_identity.provider import (IdentityProvider, PermanentProviderError, ProviderUser, TransientProviderError,
                                    UserAttributes)

log = logging.getLogger("asaa.identity.keycloak")
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
REQUIRED_ACTIONS = ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]
REFERENCE_ATTRIBUTE = "asaa_employee_reference"

Transport = Callable[[str, str, dict, "bytes | None", float], "tuple[int, dict, bytes]"]


def default_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float):
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - scheme validated in KeycloakClient
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


class KeycloakClient:
    """Token handling plus an Admin API request layer with retry/backoff. `transport` and `sleep` are injectable for tests."""

    def __init__(self, base_url: str, realm: str, client_id: str, client_secret: str, timeout: float = 10.0, max_retries: int = 4,
                 backoff_base: float = 0.5, backoff_cap: float = 30.0, sleep: Callable[[float], None] = time.sleep,
                 transport: Transport = default_transport, rng: random.Random | None = None, clock: Callable[[], float] = time.monotonic):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Keycloak URL must be an http(s) URL")
        if parsed.scheme != "https" and parsed.hostname not in LOOPBACK:
            raise ValueError("Keycloak URL must use HTTPS (HTTP is allowed only for loopback)")
        if not realm or not client_id or not client_secret:
            raise ValueError("Keycloak realm, client id and client secret are required")
        self.base_url, self.realm, self.client_id = base_url.rstrip("/"), realm, client_id
        self._secret = client_secret
        self.timeout, self.max_retries = timeout, max_retries
        self.backoff_base, self.backoff_cap, self.sleep = backoff_base, backoff_cap, sleep
        self.transport, self.rng, self.clock = transport, rng or random.Random(), clock
        self._token: str | None = None
        self._token_expires = 0.0
        self.attempts = 0

    def __repr__(self) -> str:  # never expose the secret through repr/logging of the client
        return f"KeycloakClient(base_url={self.base_url!r}, realm={self.realm!r}, client_id={self.client_id!r})"

    # ---- tokens -------------------------------------------------------------
    def _fetch_token(self) -> str:
        form = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self._secret}).encode()
        url = f"{self.base_url}/realms/{urllib.parse.quote(self.realm)}/protocol/openid-connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        status, _, raw = self._send_with_retry("POST", url, headers, form, "token request")
        if status != 200:
            raise PermanentProviderError(f"Keycloak token request was rejected (HTTP {status}); check the service-account client and secret")
        try:
            body = json.loads(raw)
            token, lifetime = body["access_token"], float(body.get("expires_in", 60))
        except (ValueError, KeyError, TypeError):
            raise PermanentProviderError("Keycloak token response was not understood") from None
        self._token, self._token_expires = token, self.clock() + max(5.0, lifetime - 30.0)
        return token

    def _bearer(self, force: bool = False) -> str:
        if force or self._token is None or self.clock() >= self._token_expires:
            return self._fetch_token()
        return self._token

    # ---- low level ---------------------------------------------------------
    def _send_with_retry(self, method: str, url: str, headers: dict, body: bytes | None, what: str):
        for attempt in range(self.max_retries + 1):
            self.attempts += 1
            retry_after: float | None = None
            try:
                status, response_headers, raw = self.transport(method, url, headers, body, self.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                failure = TransientProviderError(f"Keycloak {what} failed: {type(exc).__name__}")
            else:
                if status != 429 and status < 500:
                    return status, response_headers, raw
                header = {k.lower(): v for k, v in response_headers.items()}.get("retry-after")
                retry_after = float(header) if header and header.replace(".", "", 1).isdigit() else None
                failure = TransientProviderError(f"Keycloak {what} -> HTTP {status}")
            if attempt == self.max_retries:
                raise failure
            delay = retry_after if retry_after is not None else min(self.backoff_cap, self.backoff_base * (2 ** attempt))
            self.sleep(delay + self.rng.uniform(0, delay * 0.1))
        raise AssertionError("unreachable")

    def request(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        """Admin API call under /admin/realms/<realm>. Returns (status, headers, parsed JSON or None). 404 and 409 are returned."""
        url = f"{self.base_url}/admin/realms/{urllib.parse.quote(self.realm)}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        what = f"{method} {path.split('?')[0]}"
        for authentication in range(2):
            headers = {"Authorization": f"Bearer {self._bearer(force=authentication == 1)}", "Accept": "application/json"}
            if data is not None:
                headers["Content-Type"] = "application/json"
            status, response_headers, raw = self._send_with_retry(method, url, headers, data, what)
            if status == 401 and authentication == 0:
                self._token = None  # expired or revoked: authenticate again once
                continue
            break
        if status in (401, 403):
            raise PermanentProviderError(f"Keycloak {what} not authorized (HTTP {status}); check the service-account roles")
        if status >= 400 and status not in (404, 409):
            raise PermanentProviderError(f"Keycloak {what} -> HTTP {status}")
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return status, response_headers, parsed


def _is_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def _split_name(attributes: UserAttributes) -> tuple[str | None, str | None]:
    if attributes.first_name or attributes.last_name:
        return attributes.first_name, attributes.last_name
    if not attributes.display_name:
        return None, None
    first, _, last = attributes.display_name.strip().partition(" ")
    return first, (last.strip() or "-")


class KeycloakIdentityProvider(IdentityProvider):
    """Keycloak usernames are case-insensitive and stored lower-case; ASAA subjects should therefore be lower-case."""

    def __init__(self, client: KeycloakClient, group_prefix: str = "asaa:", base_group: str = "employees", page_size: int = 100):
        self.client, self.prefix, self.base_group, self.page_size = client, group_prefix, base_group, page_size

    # ---- lookups -------------------------------------------------------------
    def _find_user(self, subject: str) -> dict | None:
        username = subject.lower()
        _, _, users = self.client.request("GET", "/users", query={"username": username, "exact": "true"})
        for user in users or []:
            if str(user.get("username", "")).lower() == username:
                return user
        return None

    def _find_group(self, name: str, create: bool = False) -> dict | None:
        def lookup():
            _, _, groups = self.client.request("GET", "/groups", query={"search": name, "exact": "true"})
            return next((g for g in groups or [] if g.get("name") == name), None)

        group = lookup()
        if group or not create:
            return group
        status, _, _ = self.client.request("POST", "/groups", {"name": name})
        if status in (201, 204, 409):  # 409: created concurrently
            group = lookup()
            if group:
                return group
        raise PermanentProviderError("Keycloak group could not be created")

    def _groups_of(self, user_id: str) -> list[dict]:
        _, _, groups = self.client.request("GET", f"/users/{user_id}/groups")
        return groups or []

    def _managed(self, user_id: str) -> frozenset[str]:
        return frozenset(g["name"][len(self.prefix):] for g in self._groups_of(user_id) if str(g.get("name", "")).startswith(self.prefix))

    def _add_to_group(self, user_id: str, group_name: str) -> None:
        group = self._find_group(group_name, create=True)
        self.client.request("PUT", f"/users/{user_id}/groups/{group['id']}")

    # ---- representation ----------------------------------------------------------
    def _representation(self, subject: str, attributes: UserAttributes, active: bool, existing: dict | None) -> dict:
        first, last = _split_name(attributes)
        rep = dict(existing or {})
        rep.update({"username": subject.lower(), "enabled": active})
        if attributes.email:
            rep["email"] = attributes.email
        if first:
            rep["firstName"] = first
        if last:
            rep["lastName"] = last
        merged = dict(rep.get("attributes") or {})
        if attributes.employee_reference:
            merged[REFERENCE_ATTRIBUTE] = [attributes.employee_reference]
        if merged:
            rep["attributes"] = merged
        rep.pop("credentials", None)  # ASAA never sends credentials, not even ones read back
        return rep

    # ---- contract ------------------------------------------------------------------
    def upsert_user(self, subject: str, attributes: UserAttributes, active: bool) -> None:
        existing = self._find_user(subject)
        if existing is None:
            body = self._representation(subject, attributes, active, None)
            body["emailVerified"] = False
            body["requiredActions"] = list(REQUIRED_ACTIONS)
            if _is_uuid(subject):
                body["id"] = subject.lower()  # keeps the token `sub` equal to the ASAA subject
            status, headers, _ = self.client.request("POST", "/users", body)
            if status == 201:
                existing = self._find_user(subject)
                if existing is None:
                    raise TransientProviderError("Keycloak user was created but is not visible yet")
                self._add_to_group(existing["id"], self.base_group)
                return
            if status == 409:  # created concurrently, or the username/email already belongs to someone: resolve below
                existing = self._find_user(subject)
            if existing is None:
                raise PermanentProviderError("Keycloak refused to create the user (username or email conflict)")
        body = self._representation(subject, attributes, active, existing)
        status, _, _ = self.client.request("PUT", f"/users/{existing['id']}", body)
        if status == 404:
            raise TransientProviderError("Keycloak user disappeared during update")
        if status == 409:
            raise PermanentProviderError("Keycloak refused the update (email conflict)")
        if active:
            self._add_to_group(existing["id"], self.base_group)

    def disable_user(self, subject: str) -> None:
        user = self._find_user(subject)
        if user is None or user.get("enabled") is False:
            return
        status, _, _ = self.client.request("PUT", f"/users/{user['id']}", {**user, "enabled": False})
        if status == 409:
            raise PermanentProviderError("Keycloak refused to disable the user")

    def set_entitlements(self, subject: str, entitlements: frozenset[str]) -> None:
        user = self._find_user(subject)
        if user is None:
            raise PermanentProviderError("Keycloak user does not exist")
        wanted = frozenset(entitlements)
        current = self._managed(user["id"])
        for name in sorted(wanted - current):
            group = self._find_group(self.prefix + name, create=True)
            self.client.request("PUT", f"/users/{user['id']}/groups/{group['id']}")
        for name in sorted(current - wanted):
            group = self._find_group(self.prefix + name)
            if group is not None:
                self.client.request("DELETE", f"/users/{user['id']}/groups/{group['id']}")

    def revoke_sessions(self, subject: str) -> None:
        user = self._find_user(subject)
        if user is not None:
            self.client.request("POST", f"/users/{user['id']}/logout")

    def get_user(self, subject: str) -> ProviderUser | None:
        user = self._find_user(subject)
        return self._to_user(user) if user else None

    def list_users(self) -> list[ProviderUser]:
        users, first = [], 0
        while True:
            _, _, page = self.client.request("GET", "/users", query={"first": first, "max": self.page_size})
            page = page or []
            users.extend(page)
            first += len(page)
            if len(page) < self.page_size:
                return [self._to_user(u) for u in users]

    def _to_user(self, user: dict) -> ProviderUser:
        return ProviderUser(str(user.get("username", "")), bool(user.get("enabled", False)), self._managed(user["id"]))
