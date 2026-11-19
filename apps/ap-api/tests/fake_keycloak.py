"""MOCK Keycloak: an in-memory stand-in for the Admin REST API that plugs into KeycloakClient(transport=...).
No network, no real Keycloak. It records every request so tests can assert what ASAA sent (and never sent)."""
import json
import re
import urllib.parse
import uuid


class FakeKeycloak:
    def __init__(self, secret="test-client-secret", token_lifetime=300, honor_client_id=True):
        self.secret, self.token_lifetime = secret, token_lifetime
        self.honor_client_id = honor_client_id  # real Keycloak versions differ: False simulates one that ignores a supplied id
        self.group_roles: dict[str, dict] = {}   # group id -> role mappings document
        self.users: dict[str, dict] = {}
        self.groups: dict[str, dict] = {}
        self.memberships: dict[str, set] = {}
        self.sessions: dict[str, int] = {}
        self.requests: list[dict] = []
        self.token_issued = 0
        self.valid_tokens: set[str] = set()
        self.faults: list[tuple] = []  # (matcher, response or exception), consumed in order
        self.token_fault: int | None = None

    # ---- helpers for tests
    def add_group(self, name):
        gid = str(uuid.uuid4())
        self.groups[gid] = {"id": gid, "name": name, "path": "/" + name}
        return gid

    def fail(self, method, path_regex, status, times=1, headers=None, body=b"{}"):
        self.faults.append([method, re.compile(path_regex), status, times, headers or {}, body])

    def expire_tokens(self):
        self.valid_tokens.clear()

    def user_by_name(self, username):
        return next((u for u in self.users.values() if u["username"] == username), None)

    # ---- transport
    def __call__(self, method, url, headers, body, timeout):
        parsed = urllib.parse.urlparse(url)
        self.requests.append({"method": method, "path": parsed.path, "query": parsed.query, "headers": dict(headers),
                              "body": body.decode() if body else None})
        if parsed.path.endswith("/protocol/openid-connect/token"):
            return self._token(body)
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        if token not in self.valid_tokens:
            return 401, {}, b'{"error":"HTTP 401 Unauthorized"}'
        for fault in self.faults:
            if fault[0] == method and fault[1].search(parsed.path) and fault[3] > 0:
                fault[3] -= 1
                return fault[2], dict(fault[4]), fault[5]
        path = parsed.path.split("/admin/realms/asaa", 1)[1]
        query = dict(urllib.parse.parse_qsl(parsed.query))
        payload = json.loads(body) if body else None
        return self._route(method, path, query, payload)

    def _token(self, body):
        form = dict(urllib.parse.parse_qsl(body.decode()))
        if self.token_fault:
            return self.token_fault, {}, b"{}"
        if form.get("grant_type") != "client_credentials" or form.get("client_secret") != self.secret:
            return 401, {}, b'{"error":"unauthorized_client"}'
        self.token_issued += 1
        token = f"tok-{self.token_issued}"
        self.valid_tokens.add(token)
        return 200, {}, json.dumps({"access_token": token, "expires_in": self.token_lifetime, "token_type": "Bearer"}).encode()

    def _json(self, status, value=None, headers=None):
        return status, dict(headers or {}), (json.dumps(value).encode() if value is not None else b"")

    def _route(self, method, path, query, payload):
        if path == "/users" and method == "GET":
            if "username" in query:
                found = [u for u in self.users.values() if u["username"] == query["username"]]
                return self._json(200, found)
            if "q" in query:
                name, _, value = query["q"].partition(":")
                found = [u for u in self.users.values() if value in (u.get("attributes") or {}).get(name, [])]
                return self._json(200, found)
            first, count = int(query.get("first", 0)), int(query.get("max", 100))
            return self._json(200, list(self.users.values())[first:first + count])
        if path == "/users" and method == "POST":
            username = payload["username"]
            if self.user_by_name(username) or any(u.get("email") and u.get("email") == payload.get("email") for u in self.users.values()):
                return self._json(409, {"errorMessage": "User exists with same username"})
            user = {**payload, "id": (payload.get("id") if self.honor_client_id else None) or str(uuid.uuid4())}
            self.users[user["id"]] = user
            self.memberships[user["id"]] = set()
            return self._json(201, None, {"Location": f".../users/{user['id']}"})
        m = re.fullmatch(r"/users/([^/]+)", path)
        if m:
            user = self.users.get(m.group(1))
            if not user:
                return self._json(404, {"error": "User not found"})
            if method == "PUT":
                merged = {**user, **payload, "id": user["id"]}  # Keycloak applies the supplied fields and keeps the others
                self.users[user["id"]] = merged
                return self._json(204)
            if method == "GET":
                return self._json(200, user)
        m = re.fullmatch(r"/users/([^/]+)/logout", path)
        if m and method == "POST":
            if m.group(1) not in self.users:
                return self._json(404, {"error": "User not found"})
            self.sessions[m.group(1)] = self.sessions.get(m.group(1), 0) + 1
            return self._json(204)
        m = re.fullmatch(r"/users/([^/]+)/groups", path)
        if m and method == "GET":
            return self._json(200, [self.groups[g] for g in sorted(self.memberships.get(m.group(1), set()))])
        m = re.fullmatch(r"/users/([^/]+)/groups/([^/]+)", path)
        if m and method in {"PUT", "DELETE"}:
            members = self.memberships.setdefault(m.group(1), set())
            (members.add if method == "PUT" else members.discard)(m.group(2))
            return self._json(204)
        m = re.fullmatch(r"/groups/([^/]+)/role-mappings", path)
        if m and method == "GET":
            return self._json(200, self.group_roles.get(m.group(1), {}))
        if path == "/groups" and method == "GET":
            return self._json(200, [g for g in self.groups.values() if query.get("search", "") in g["name"]])
        if path == "/groups" and method == "POST":
            if any(g["name"] == payload["name"] for g in self.groups.values()):
                return self._json(409, {"errorMessage": "Top level group named exists"})
            gid = self.add_group(payload["name"])
            return self._json(201, None, {"Location": f".../groups/{gid}"})
        return self._json(404, {"error": f"unrouted {method} {path}"})
