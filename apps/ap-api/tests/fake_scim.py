"""A small local SCIM 2.0 server for tests: Users/Groups, filter eq, paging, ETag/If-Match, fault injection."""
import json
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def unescape(value):
    out, i = [], 0
    while i < len(value):
        if value[i] == chr(92) and i + 1 < len(value):
            i += 1
        out.append(value[i])
        i += 1
    return "".join(out)


class FakeScim:
    def __init__(self, token="test-token", page_cap=2):
        self.token, self.page_cap = token, page_cap
        self.users: dict[str, dict] = {}
        self.groups: dict[str, dict] = {}
        self.faults: list[tuple[int, dict]] = []  # (status, headers) consumed one per request
        self.requests: list[tuple[str, str, dict]] = []
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.server.server_port}/scim/v2"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    # --- state helpers -------------------------------------------------------
    def _touch(self, item):
        item["_v"] = item.get("_v", 0) + 1

    def _render(self, kind, item):
        out = {k: v for k, v in item.items() if not k.startswith("_")}
        out["meta"] = {"resourceType": kind, "version": f'W/"{item["_v"]}"'}
        if kind == "User":
            out["groups"] = [{"value": g["id"], "display": g["displayName"]} for g in self.groups.values()
                             if any(m["value"] == item["id"] for m in g.get("members", []))]
        return out

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, body=None, headers=None):
                payload = json.dumps(body).encode() if body is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/scim+json")
                self.send_header("Content-Length", str(len(payload)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(payload)

            def _body(self):
                length = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(length)) if length else {}

            def _route(self, method):
                parsed = urlparse(self.path)
                body = self._body() if method in ("POST", "PATCH", "PUT") else {}
                with fake.lock:
                    fake.requests.append((method, parsed.path, body))
                    if fake.faults:
                        status, headers = fake.faults.pop(0)
                        return self._send(status, {"detail": "injected"}, headers)
                    if self.headers.get("Authorization") != f"Bearer {fake.token}":
                        return self._send(401, {"detail": "unauthorized"})
                    m = re.match(r"^/scim/v2/(Users|Groups)(?:/([^/]+))?$", parsed.path)
                    if not m:
                        return self._send(404, {"detail": "not found"})
                    kind, rid = m.group(1), m.group(2)
                    store, name = (fake.users, "User") if kind == "Users" else (fake.groups, "Group")
                    if method == "GET" and rid is None:
                        return self._list(store, name, parse_qs(parsed.query))
                    if method == "GET":
                        return self._send(200, fake._render(name, store[rid])) if rid in store else self._send(404, {})
                    if method == "POST":
                        key = "userName" if name == "User" else "displayName"
                        if any(i.get(key) == body.get(key) for i in store.values()):
                            return self._send(409, {"scimType": "uniqueness"})
                        item = {**body, "id": str(uuid.uuid4())}
                        if name == "Group":
                            item.setdefault("members", [])
                        fake._touch(item)
                        store[item["id"]] = item
                        return self._send(201, fake._render(name, item))
                    if method == "PATCH":
                        item = store.get(rid)
                        if item is None:
                            return self._send(404, {})
                        match = self.headers.get("If-Match")
                        if match and match != f'W/"{item["_v"]}"':
                            return self._send(412, {"scimType": "preconditionFailed"})
                        for op in body.get("Operations", []):
                            self._apply(item, op)
                        fake._touch(item)
                        return self._send(200, fake._render(name, item))
                return self._send(405, {})

            def _apply(self, item, op):
                path, value, kind = op.get("path", ""), op.get("value"), op["op"].lower()
                if path == "members":
                    if kind == "add":
                        for member in value:
                            if not any(x["value"] == member["value"] for x in item["members"]):
                                item["members"].append(member)
                elif path.startswith("members[value eq"):
                    target = re.search(r'"(.*)"', path).group(1)
                    item["members"] = [x for x in item["members"] if x["value"] != target]
                else:
                    item[path] = value

            def _list(self, store, name, query):
                items = list(store.values())
                flt = (query.get("filter") or [""])[0]
                m = re.match(r'^(\w+) eq "(.*)"$', flt)
                if m:
                    items = [i for i in items if i.get(m.group(1)) == unescape(m.group(2))]
                start = int((query.get("startIndex") or ["1"])[0])
                count = min(int((query.get("count") or ["100"])[0]), fake.page_cap)
                page = items[start - 1:start - 1 + count]
                return self._send(200, {"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "totalResults": len(items),
                                        "startIndex": start, "itemsPerPage": len(page), "Resources": [fake._render(name, i) for i in page]})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PATCH(self):
                self._route("PATCH")

        return Handler
