"""Keycloak identity provider adapter (Admin REST API, service-account client credentials).

ASAA HR lifecycle drives the single-sign-on accounts:
  joiner     create the user (username, email, first/last name from HR, enabled, required actions UPDATE_PASSWORD and
             CONFIGURE_TOTP) and add it to the base group. ASAA NEVER sets or sends a password or any credential.
  mover      update attributes and replace the managed groups.
  leaver     disable the user and log out all sessions. A leaver whose account cannot be found is NOT a success: it raises
             ProviderUserNotFound so the job gets the distinct NotFound outcome and an alert.

Ownership: ASAA only touches accounts it created. Every account carries the attributes asaa_managed=true and asaa_subject; an
existing account is adopted only when those markers (or a matching asaa_employee_reference) say it is ASAA's. An account that was
disabled outside ASAA (for example by the security team) is never re-enabled by a mover or by reconciliation; only an explicit
joiner/re-hire may do that. Subjects that collide after Keycloak lower-cases usernames are refused.

Entitlement "x" maps to the group "<group_prefix>x". The prefix must be non-empty, protected group names are refused, entitlement
names are validated, groups are not created unless explicitly enabled, and a group that carries role mappings is never used for
entitlements (a group-membership step must not be able to grant realm or client roles).

Reliability follows the identity worker contract: network failures, HTTP protocol errors, 429 and 5xx retry with capped backoff
under a total per-request deadline and then raise TransientProviderError. A refused credential (token request, 401 after one
refresh, 403) raises AuthenticationProviderError (transient, long backoff, alert; never dead-letters a leaver). Redirects are
never followed (a 3xx is a permanent error), responses are size-capped, and the client secret and tokens never appear in logs or
exception messages.
"""
from __future__ import annotations

import fnmatch
import http.client
import json
import logging
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Callable

from asaa_identity.provider import (AuthenticationProviderError, IdentityProvider, PermanentProviderError, ProviderUser,
                                    ProviderUserNotFound, TransientProviderError, UserAttributes)

log = logging.getLogger("asaa.identity.keycloak")
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
REQUIRED_ACTIONS = ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]
MANAGED_ATTRIBUTE = "asaa_managed"
SUBJECT_ATTRIBUTE = "asaa_subject"
REFERENCE_ATTRIBUTE = "asaa_employee_reference"
DISABLED_BY_ASAA_ATTRIBUTE = "asaa_disabled_by_asaa"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
PROTECTED_GROUPS = ("asaa-administrators", "hr", "payroll", "finance", "managers", "auditors", "realm-management",
                    "jarvis-*", "portfolio-*", "templates-*")
_REALM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_ENTITLEMENT = re.compile(r"^[a-z][a-z0-9_.:-]{1,127}\Z")
_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,31}\Z")
_GROUP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}\Z")

Transport = Callable[[str, str, dict, "bytes | None", float], "tuple[int, dict, bytes]"]


def is_protected_group(name: str) -> bool:
    """True for names that confer privilege in the surrounding realm; they may never be used as the prefix, base group or entitlement."""
    lowered = name.strip().strip("/").lower()
    return any(fnmatch.fnmatchcase(lowered, pattern) for pattern in PROTECTED_GROUPS)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - never follow a redirect: it could carry the bearer token elsewhere
        return None


def default_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(request, timeout=timeout) as response:  # noqa: S310 - scheme validated in KeycloakClient
            return response.status, dict(response.headers), response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:  # includes unfollowed 3xx
        return exc.code, dict(exc.headers), exc.read(MAX_RESPONSE_BYTES + 1)


def _quote(value) -> str:
    return urllib.parse.quote(str(value), safe="")


class KeycloakClient:
    """Token handling plus an Admin API request layer with retry/backoff. `transport`, `sleep` and `clock` are injectable for tests."""

    def __init__(self, base_url: str, realm: str, client_id: str, client_secret: str, timeout: float = 10.0, max_retries: int = 4,
                 backoff_base: float = 0.5, backoff_cap: float = 30.0, max_total_seconds: float = 60.0,
                 sleep: Callable[[float], None] = time.sleep, transport: Transport = default_transport,
                 rng: random.Random | None = None, clock: Callable[[], float] = time.monotonic):
        parsed = urllib.parse.urlparse(base_url)
        try:
            hostname = parsed.hostname
        except ValueError:
            hostname = None
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise ValueError("Keycloak URL must be an http(s) URL")
        try:
            parsed.port  # noqa: B018 - raises for a malformed port such as "8280;p=1"
        except ValueError:
            raise ValueError("Keycloak URL has an invalid port") from None
        if (parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.params
                or not re.fullmatch(r"[A-Za-z0-9.\-\[\]:]+", parsed.netloc)):
            raise ValueError("Keycloak URL must not contain credentials, parameters, a query or a fragment")
        if parsed.scheme != "https" and hostname not in LOOPBACK:
            raise ValueError("Keycloak URL must use HTTPS (HTTP is allowed only for loopback)")
        if not _REALM.match(realm or ""):
            raise ValueError("Keycloak realm name is invalid")
        if not client_id or not client_secret:
            raise ValueError("Keycloak client id and client secret are required")
        self.base_url, self.realm, self.client_id = base_url.rstrip("/"), realm, client_id
        self._secret = client_secret
        self.timeout, self.max_retries, self.max_total_seconds = timeout, max_retries, max_total_seconds
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
        url = f"{self.base_url}/realms/{_quote(self.realm)}/protocol/openid-connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        status, _, raw = self._send_with_retry("POST", url, headers, form, "token request")
        if status in (400, 401, 403, 404):
            raise AuthenticationProviderError(f"Keycloak refused the service-account credentials (HTTP {status}); check the client, its secret and the realm")
        if status != 200:
            raise PermanentProviderError(f"Keycloak token request failed (HTTP {status})")
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
        deadline = self.clock() + self.max_total_seconds
        for attempt in range(self.max_retries + 1):
            self.attempts += 1
            retry_after: float | None = None
            try:
                status, response_headers, raw = self.transport(method, url, headers, body, self.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException) as exc:
                failure = TransientProviderError(f"Keycloak {what} failed: {type(exc).__name__}")
            else:
                if 300 <= status < 400:
                    raise PermanentProviderError(f"Keycloak {what} -> unexpected redirect (HTTP {status}); redirects are never followed")
                if len(raw or b"") > MAX_RESPONSE_BYTES:
                    raise PermanentProviderError(f"Keycloak {what} response exceeded the size limit")
                if status != 429 and status < 500:
                    return status, response_headers, raw
                header = {k.lower(): v for k, v in response_headers.items()}.get("retry-after")
                retry_after = float(header) if header and header.replace(".", "", 1).isdigit() else None
                failure = TransientProviderError(f"Keycloak {what} -> HTTP {status}")
            if attempt == self.max_retries:
                raise failure
            delay = min(self.backoff_cap, retry_after if retry_after is not None else self.backoff_base * (2 ** attempt))
            if self.clock() + delay > deadline:  # total per-request deadline: give up now, the outbox retries later
                raise failure
            self.sleep(delay + self.rng.uniform(0, delay * 0.1))
        raise AssertionError("unreachable")

    def request(self, method: str, path: str, body: dict | None = None, query: dict | None = None):
        """Admin API call under /admin/realms/<realm>. Returns (status, headers, parsed JSON or None). 404 and 409 are returned."""
        url = f"{self.base_url}/admin/realms/{_quote(self.realm)}{path}"
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
            raise AuthenticationProviderError(f"Keycloak {what} not authorized (HTTP {status}); check the service-account roles")
        if status >= 400 and status not in (404, 409):
            raise PermanentProviderError(f"Keycloak {what} -> HTTP {status}")
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
            if method == "GET" and status == 200:
                raise TransientProviderError(f"Keycloak {what} returned a non-JSON answer (an intermediary or login page?)") from None
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


def _first(attributes: dict | None, name: str) -> str | None:
    values = (attributes or {}).get(name) or []
    return str(values[0]) if values else None


class KeycloakIdentityProvider(IdentityProvider):
    """Keycloak usernames are case-insensitive and stored lower-case; ASAA subjects are kept verbatim in the asaa_subject attribute."""

    def __init__(self, client: KeycloakClient, group_prefix: str = "asaa:", base_group: str = "employees", page_size: int = 100,
                 create_groups: bool = False, base_group_roles: "frozenset[str] | set[str] | list[str]" = frozenset()):
        if not _PREFIX.match(group_prefix or ""):
            raise ValueError("The Keycloak entitlement group prefix must be non-empty (letters, digits and ._:/-, at most 32 characters)")
        if not _GROUP_NAME.match(base_group or ""):
            raise ValueError("The Keycloak base group name is invalid")
        for label, name in (("prefix", group_prefix.rstrip(":/._-")), ("base group", base_group)):
            if name and is_protected_group(name):
                raise ValueError(f"The Keycloak {label} {name!r} is a protected group name and cannot be used by identity sync")
        self.client, self.prefix, self.base_group, self.page_size = client, group_prefix, base_group, page_size
        self.create_groups = create_groups
        # Roles the base group may map: realm roles by name, client roles as "client/role". None by default: a membership step must
        # not be able to confer roles, so a base group with any other role mapping is refused.
        self.base_group_roles = frozenset(base_group_roles)
        self._steps: list[dict] = []

    # ---- audit -----------------------------------------------------------------
    def _step(self, subject: str, provider_id: str | None, action: str, **extra) -> None:
        self._steps.append({"subject": subject, "provider_id": provider_id, "action": action, **{k: v for k, v in extra.items() if v}})

    def drain_audit(self) -> list[dict]:
        steps, self._steps = self._steps, []
        return steps

    # ---- lookups -------------------------------------------------------------
    def _owned(self, user: dict, subject: str, reference: str | None = None) -> bool:
        attributes = user.get("attributes") or {}
        if _first(attributes, MANAGED_ATTRIBUTE) != "true":
            return False
        if _first(attributes, SUBJECT_ATTRIBUTE) == subject:
            return True
        return bool(reference) and _first(attributes, REFERENCE_ATTRIBUTE) == reference

    def _search_attribute(self, name: str, value: str) -> list[dict]:
        _, _, users = self.client.request("GET", "/users", query={"q": f"{name}:{value}", "exact": "true"})
        return [u for u in users or [] if _first(u.get("attributes"), name) == value]

    def _resolve(self, subject: str, reference: str | None = None) -> tuple[dict | None, bool]:
        """(user, owned). Order: Keycloak id (when the subject is a UUID), username, asaa_subject attribute, employee reference."""
        if _is_uuid(subject):
            status, _, user = self.client.request("GET", f"/users/{_quote(subject.lower())}")
            if status == 200 and isinstance(user, dict):
                return user, self._owned(user, subject, reference)
        username = subject.lower()
        _, _, users = self.client.request("GET", "/users", query={"username": username, "exact": "true"})
        for user in users or []:
            if str(user.get("username", "")).lower() == username:
                if not self._owned(user, subject, reference):
                    return user, False  # a same-named account that ASAA does not own: never adopt it
                return user, True
        for attribute, value in ((SUBJECT_ATTRIBUTE, subject), (REFERENCE_ATTRIBUTE, reference)):
            if not value:
                continue
            matches = [u for u in self._search_attribute(attribute, value) if _first(u.get("attributes"), MANAGED_ATTRIBUTE) == "true"]
            if len(matches) > 1:
                raise PermanentProviderError("More than one ASAA-managed Keycloak account matches this employee; resolve it manually")
            if matches:
                return matches[0], True
        return None, False

    def _find_group(self, name: str, allowed_roles: frozenset = frozenset()) -> dict:
        _, _, groups = self.client.request("GET", "/groups", query={"search": name, "exact": "true"})
        group = next((g for g in groups or [] if g.get("name") == name), None)
        if group is None:
            if not self.create_groups:
                raise PermanentProviderError("Keycloak group does not exist and group creation is disabled")
            status, _, _ = self.client.request("POST", "/groups", {"name": name})
            if status not in (201, 204, 409):
                raise PermanentProviderError("Keycloak group could not be created")
            _, _, groups = self.client.request("GET", "/groups", query={"search": name, "exact": "true"})
            group = next((g for g in groups or [] if g.get("name") == name), None)
            if group is None:
                raise TransientProviderError("Keycloak group was created but is not visible yet")
        _, _, mappings = self.client.request("GET", f"/groups/{_quote(group['id'])}/role-mappings")
        mappings = mappings or {}
        mapped = {str(r.get("name")) for r in mappings.get("realmMappings") or []}
        for client_id, doc in (mappings.get("clientMappings") or {}).items():
            mapped |= {f"{client_id}/{r.get('name')}" for r in (doc or {}).get("mappings") or []}
        if mapped - set(allowed_roles):
            raise PermanentProviderError("Keycloak group carries role mappings outside its allow-list and will not be used")
        return group

    def _groups_of(self, user_id: str) -> list[dict]:
        _, _, groups = self.client.request("GET", f"/users/{_quote(user_id)}/groups")
        return groups or []

    def _managed(self, user_id: str) -> frozenset[str]:
        return frozenset(g["name"][len(self.prefix):] for g in self._groups_of(user_id) if str(g.get("name", "")).startswith(self.prefix))

    def _group_write(self, method: str, user_id: str, group_id: str) -> None:
        status, _, _ = self.client.request(method, f"/users/{_quote(user_id)}/groups/{_quote(group_id)}")
        if status == 404:
            raise TransientProviderError("Keycloak user or group disappeared during a membership change")
        if status not in (200, 204):
            raise PermanentProviderError(f"Keycloak group membership change returned HTTP {status}")

    def _ensure_base_group(self, user_id: str) -> None:
        group = self._find_group(self.base_group, allowed_roles=self.base_group_roles)
        self._group_write("PUT", user_id, group["id"])

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
        merged.update({MANAGED_ATTRIBUTE: ["true"], SUBJECT_ATTRIBUTE: [subject]})
        if attributes.employee_reference:
            merged[REFERENCE_ATTRIBUTE] = [attributes.employee_reference]
        if active:
            merged.pop(DISABLED_BY_ASAA_ATTRIBUTE, None)
        rep["attributes"] = merged
        rep.pop("credentials", None)  # ASAA never sends credentials, not even ones read back
        return rep

    # ---- contract ------------------------------------------------------------------
    def upsert_user(self, subject: str, attributes: UserAttributes, active: bool) -> str:
        existing, owned = self._resolve(subject, attributes.employee_reference)
        if existing is None:
            body = self._representation(subject, attributes, active, None)
            body["emailVerified"] = False
            body["requiredActions"] = list(REQUIRED_ACTIONS)
            if _is_uuid(subject):
                body["id"] = subject.lower()  # honoured by some Keycloak versions; the id actually assigned is read back below
            status, headers, _ = self.client.request("POST", "/users", body)
            if status == 409:  # created concurrently, or a username/email conflict: decide below
                existing, owned = self._resolve(subject, attributes.employee_reference)
                if existing is None:
                    raise PermanentProviderError("Keycloak refused to create the user (username or email conflict)")
            elif status == 201:
                created, _ = self._resolve(subject, attributes.employee_reference)
                if created is None:
                    raise TransientProviderError("Keycloak user was created but is not visible yet")
                self._ensure_base_group(created["id"])
                self._step(subject, created["id"], "created")
                if _is_uuid(subject) and created["id"].lower() != subject.lower():
                    log.warning("keycloak_id_differs_from_subject", extra={"subject": subject})
                    self._step(subject, created["id"], "id_differs_from_subject")
                return created["id"]
            else:
                raise PermanentProviderError(f"Keycloak refused to create the user (HTTP {status})")
        if not owned:
            raise PermanentProviderError("An existing Keycloak account matches this subject but is not managed by ASAA; it will not be adopted")
        recorded = _first(existing.get("attributes"), SUBJECT_ATTRIBUTE)
        if recorded is not None and recorded != subject:
            raise PermanentProviderError("This subject collides with another ASAA subject after Keycloak lower-cases usernames")
        reenabled = False
        if active and existing.get("enabled") is False:
            by_asaa = _first(existing.get("attributes"), DISABLED_BY_ASAA_ATTRIBUTE) == "true"
            if not (by_asaa or attributes.allow_reenable):
                raise PermanentProviderError("The account was disabled outside ASAA; only an explicit re-hire may re-enable it")
            reenabled = True
        body = self._representation(subject, attributes, active, existing)
        status, _, _ = self.client.request("PUT", f"/users/{_quote(existing['id'])}", body)
        if status == 404:
            raise TransientProviderError("Keycloak user disappeared during update")
        if status == 409:
            raise PermanentProviderError("Keycloak refused the update (email conflict)")
        if status not in (200, 204):
            raise PermanentProviderError(f"Keycloak refused the update (HTTP {status})")
        if active:
            self._ensure_base_group(existing["id"])
        self._step(subject, existing["id"], "enabled" if reenabled else "updated")
        return existing["id"]

    def adopt_account(self, subject: str, username: str, employee_reference: str | None, employee_email: str | None) -> str:
        """Mark a pre-existing account as ASAA-managed. Only called after an independent approval. The account must exist under the
        given username, must not already be managed (by anyone), and must prove it belongs to this employee: its
        asaa_employee_reference attribute equals the HR employee code, or (when it has none) its email equals the HR work email."""
        _, _, users = self.client.request("GET", "/users", query={"username": username.lower(), "exact": "true"})
        account = next((u for u in users or [] if str(u.get("username", "")).lower() == username.lower()), None)
        if account is None:
            raise PermanentProviderError("No Keycloak account has that username")
        attributes = dict(account.get("attributes") or {})
        if _first(attributes, MANAGED_ATTRIBUTE) == "true" or _first(attributes, SUBJECT_ATTRIBUTE) is not None:
            raise PermanentProviderError("That Keycloak account is already managed by ASAA")
        recorded = _first(attributes, REFERENCE_ATTRIBUTE)
        if recorded is not None:
            proven = bool(employee_reference) and recorded == employee_reference
        else:
            proven = bool(employee_email) and str(account.get("email", "")).lower() == employee_email.lower()
        if not proven:
            raise PermanentProviderError("The account does not match the employee (employee reference or email)")
        attributes.update({MANAGED_ATTRIBUTE: ["true"], SUBJECT_ATTRIBUTE: [subject]})
        if employee_reference:
            attributes[REFERENCE_ATTRIBUTE] = [employee_reference]
        status, _, _ = self.client.request("PUT", f"/users/{_quote(account['id'])}", {"attributes": attributes})
        if status == 404:
            raise TransientProviderError("Keycloak user disappeared during adoption")
        if status not in (200, 204):
            raise PermanentProviderError(f"Keycloak refused the adoption (HTTP {status})")
        self._step(subject, account["id"], "adopted")
        return account["id"]

    def disable_user(self, subject: str) -> None:
        user, owned = self._resolve(subject)
        if user is None:
            self._step(subject, None, "not_found", reason="leaver account not found")
            raise ProviderUserNotFound("Keycloak has no account for this subject")
        if not owned:
            raise PermanentProviderError("The matching Keycloak account is not managed by ASAA; it was not disabled")
        if user.get("enabled") is False:
            return
        attributes = dict(user.get("attributes") or {})
        attributes[DISABLED_BY_ASAA_ATTRIBUTE] = ["true"]
        status, _, _ = self.client.request("PUT", f"/users/{_quote(user['id'])}", {"enabled": False, "attributes": attributes})
        if status == 404:
            raise TransientProviderError("Keycloak user disappeared while being disabled")
        if status not in (200, 204):
            raise PermanentProviderError(f"Keycloak refused to disable the user (HTTP {status})")
        self._step(subject, user["id"], "disabled")

    def set_entitlements(self, subject: str, entitlements: frozenset[str]) -> None:
        user, owned = self._resolve(subject)
        if user is None:
            raise PermanentProviderError("Keycloak user does not exist")
        if not owned:
            raise PermanentProviderError("The matching Keycloak account is not managed by ASAA; its groups were not changed")
        wanted = frozenset(entitlements)
        for name in wanted:
            if not _ENTITLEMENT.match(name) or is_protected_group(name) or is_protected_group(self.prefix + name):
                raise PermanentProviderError("An entitlement name is invalid or maps to a protected group")
        current = self._managed(user["id"])
        added, removed = sorted(wanted - current), sorted(current - wanted)
        groups = {name: self._find_group(self.prefix + name) for name in added}  # validate every group before changing anything
        for name in added:
            self._group_write("PUT", user["id"], groups[name]["id"])
        for name in removed:
            _, _, found = self.client.request("GET", "/groups", query={"search": self.prefix + name, "exact": "true"})
            group = next((g for g in found or [] if g.get("name") == self.prefix + name), None)
            if group is not None:
                self._group_write("DELETE", user["id"], group["id"])
        if added or removed:
            self._step(subject, user["id"], "groups_changed", groups_added=[self.prefix + n for n in added],
                       groups_removed=[self.prefix + n for n in removed])

    def revoke_sessions(self, subject: str) -> None:
        user, _ = self._resolve(subject)
        if user is None:
            self._step(subject, None, "not_found", reason="no account to log out")
            return
        status, _, _ = self.client.request("POST", f"/users/{_quote(user['id'])}/logout")
        if status not in (200, 204, 404):
            raise PermanentProviderError(f"Keycloak refused to log the user out (HTTP {status})")
        if status != 404:
            self._step(subject, user["id"], "sessions_revoked")

    def get_user(self, subject: str) -> ProviderUser | None:
        user, _ = self._resolve(subject)
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
        subject = _first(user.get("attributes"), SUBJECT_ATTRIBUTE) or str(user.get("username", ""))
        return ProviderUser(subject, bool(user.get("enabled", False)), self._managed(user["id"]), user["id"])
