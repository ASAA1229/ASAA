"""SCIM 2.0 (RFC 7643/7644) identity provider adapter. Provider neutral: no tenant, vendor or schema extension is assumed.

Mapping (all configurable through the constructor)
  subject            -> User.userName (and externalId)
  active             -> User.active
  entitlement "x"    -> Group with displayName "<group_prefix>x"; membership via Group.members
Only groups whose displayName starts with group_prefix are managed, so unrelated groups are never touched.
Session revocation has no SCIM equivalent; deactivation is applied and an optional `session_revoker` hook is called
(for a provider-specific revoke API). Without a hook the adapter documents that only deactivation was performed.

Reliability: 429 (honours Retry-After) and 5xx/timeouts retry with exponential backoff + jitter, then raise
TransientProviderError so the outbox retries later; other 4xx raise PermanentProviderError. Updates use ETag/If-Match
and re-read once on 412.
"""
from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from asaa_identity.provider import (IdentityProvider, PermanentProviderError, ProviderUser, TransientProviderError,
                                    UserAttributes)

log = logging.getLogger("asaa.identity.scim")
USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class ScimClient:
    """Minimal HTTP layer with retry/backoff. `sleep` is injectable so tests do not wait."""

    def __init__(self, base_url: str, bearer_token: str | Callable[[], str], timeout: float = 10.0, max_retries: int = 4,
                 backoff_base: float = 0.5, backoff_cap: float = 30.0, sleep: Callable[[float], None] = time.sleep,
                 rng: random.Random | None = None):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("SCIM base URL must use HTTPS (HTTP is allowed only for localhost)")
        self.base_url = base_url.rstrip("/")
        self._token = bearer_token if callable(bearer_token) else (lambda: bearer_token)
        self.timeout, self.max_retries = timeout, max_retries
        self.backoff_base, self.backoff_cap, self.sleep = backoff_base, backoff_cap, sleep
        self.rng = rng or random.Random()
        self.attempts = 0  # observable by tests/metrics

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        url = self.base_url + path
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self._token()}", "Accept": "application/scim+json",
                "Content-Type": "application/scim+json", **(headers or {})})
            self.attempts += 1
            retry_after: float | None = None
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    return response.status, dict(response.headers), (json.loads(raw) if raw else None)
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                status = exc.code
                if status == 429 or status >= 500:
                    header = exc.headers.get("Retry-After")
                    retry_after = float(header) if header and header.replace(".", "", 1).isdigit() else None
                    failure = TransientProviderError(f"SCIM {method} {path.split('?')[0]} -> HTTP {status}")
                else:
                    detail = ""
                    try:
                        detail = (json.loads(raw) or {}).get("scimType") or ""
                    except (ValueError, AttributeError):
                        pass
                    if status in (404, 409, 412):  # callers decide; not an error at this layer
                        return status, dict(exc.headers), (json.loads(raw) if raw else None)
                    raise PermanentProviderError(f"SCIM {method} {path.split('?')[0]} -> HTTP {status} {detail}".strip()) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                failure = TransientProviderError(f"SCIM {method} {path.split('?')[0]} failed: {type(exc).__name__}")
            if attempt == self.max_retries:
                raise failure
            delay = retry_after if retry_after is not None else min(self.backoff_cap, self.backoff_base * (2 ** attempt))
            self.sleep(delay + self.rng.uniform(0, delay * 0.1))
        raise AssertionError("unreachable")


class ScimIdentityProvider(IdentityProvider):
    def __init__(self, client: ScimClient, group_prefix: str = "asaa:", page_size: int = 100,
                 session_revoker: Callable[[str], None] | None = None):
        self.client, self.prefix, self.page_size, self.session_revoker = client, group_prefix, page_size, session_revoker

    # ---- low level helpers --------------------------------------------------
    def _list(self, resource: str, filter_expr: str | None = None):
        start, items = 1, []
        while True:
            query = {"startIndex": start, "count": self.page_size}
            if filter_expr:
                query["filter"] = filter_expr
            status, _, body = self.client.request("GET", f"/{resource}?" + urllib.parse.urlencode(query))
            if status != 200 or not body:
                raise PermanentProviderError(f"SCIM list {resource} returned HTTP {status}")
            page = body.get("Resources") or []
            items.extend(page)
            total = body.get("totalResults", len(items))
            start += len(page)
            if not page or len(items) >= total:
                return items

    def _find_user(self, subject: str):
        users = self._list("Users", f'userName eq "{_quote(subject)}"')
        return users[0] if users else None

    def _find_group(self, name: str, create: bool = False):
        groups = self._list("Groups", f'displayName eq "{_quote(self.prefix + name)}"')
        if groups:
            return groups[0]
        if not create:
            return None
        status, _, body = self.client.request("POST", "/Groups", {"schemas": [GROUP_SCHEMA], "displayName": self.prefix + name})
        if status in (200, 201):
            return body
        if status == 409:  # created concurrently
            groups = self._list("Groups", f'displayName eq "{_quote(self.prefix + name)}"')
            if groups:
                return groups[0]
        raise PermanentProviderError(f"SCIM could not create group (HTTP {status})")

    def _patch(self, resource: str, item: dict, operations: list[dict], refetch: Callable[[], dict | None]):
        """PATCH with If-Match; on 412 re-read the resource once and retry."""
        for attempt in range(2):
            headers = {}
            etag = (item.get("meta") or {}).get("version")
            if etag:
                headers["If-Match"] = etag
            status, _, body = self.client.request("PATCH", f"/{resource}/{item['id']}", {"schemas": [PATCH_SCHEMA], "Operations": operations}, headers)
            if status == 412 and attempt == 0:
                fresh = refetch()
                if fresh is None:
                    return None
                item = fresh
                continue
            if status in (200, 204):
                return body
            if status == 404:
                return None
            raise PermanentProviderError(f"SCIM PATCH {resource} failed (HTTP {status})")
        raise TransientProviderError("SCIM resource kept changing (412); will retry later")

    def _managed(self, user: dict) -> frozenset[str]:
        names = {g.get("display", "") for g in user.get("groups") or []}
        return frozenset(n[len(self.prefix):] for n in names if n.startswith(self.prefix))

    # ---- contract ---------------------------------------------------------------
    def upsert_user(self, subject: str, attributes: UserAttributes, active: bool) -> None:
        existing = self._find_user(subject)
        emails = [{"value": attributes.email, "primary": True, "type": "work"}] if attributes.email else []
        if existing is None:
            body = {"schemas": [USER_SCHEMA], "userName": subject, "externalId": subject, "active": active}
            if attributes.display_name:
                body["displayName"] = attributes.display_name
            if emails:
                body["emails"] = emails
            if attributes.employee_reference:
                body["externalId"] = attributes.employee_reference
            status, _, _ = self.client.request("POST", "/Users", body)
            if status in (200, 201):
                return
            if status == 409:  # created concurrently: fall through to update
                existing = self._find_user(subject)
            if existing is None:
                raise PermanentProviderError(f"SCIM create user failed (HTTP {status})")
        operations = [{"op": "replace", "path": "active", "value": active}]
        if attributes.display_name:
            operations.append({"op": "replace", "path": "displayName", "value": attributes.display_name})
        if emails:
            operations.append({"op": "replace", "path": "emails", "value": emails})
        if self._patch("Users", existing, operations, lambda: self._find_user(subject)) is None:
            raise PermanentProviderError("SCIM user disappeared during update")

    def disable_user(self, subject: str) -> None:
        user = self._find_user(subject)
        if user is None:
            return
        if user.get("active") is False:
            return
        self._patch("Users", user, [{"op": "replace", "path": "active", "value": False}], lambda: self._find_user(subject))

    def set_entitlements(self, subject: str, entitlements: frozenset[str]) -> None:
        user = self._find_user(subject)
        if user is None:
            raise PermanentProviderError("SCIM user does not exist")
        current = self._managed(user)
        for name in sorted(frozenset(entitlements) - current):
            group = self._find_group(name, create=True)
            self._patch("Groups", group, [{"op": "add", "path": "members", "value": [{"value": user["id"]}]}], lambda n=name: self._find_group(n))
        for name in sorted(current - frozenset(entitlements)):
            group = self._find_group(name)
            if group is not None:
                self._patch("Groups", group, [{"op": "remove", "path": f'members[value eq "{_quote(user["id"])}"]'}], lambda n=name: self._find_group(n))

    def revoke_sessions(self, subject: str) -> None:
        if self.session_revoker is not None:
            self.session_revoker(subject)
        else:
            log.warning("scim_session_revocation_not_supported", extra={"note": "only deactivation applied; no revoke hook configured"})

    def get_user(self, subject: str) -> ProviderUser | None:
        user = self._find_user(subject)
        return self._to_user(user) if user else None

    def list_users(self) -> list[ProviderUser]:
        return [self._to_user(u) for u in self._list("Users")]

    def _to_user(self, user: dict) -> ProviderUser:
        return ProviderUser(user.get("userName", ""), bool(user.get("active", True)), self._managed(user))
