"""Baseline HTTP hardening: security response headers and a request body size limit (pure ASGI)."""
from __future__ import annotations

import json

MAX_BODY_BYTES = 1_048_576  # 1 MiB; JSON APIs here carry small payloads. Document upload will need its own limit.

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]


class HardeningMiddleware:
    def __init__(self, app, max_body_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k: v for k, v in scope["headers"]}
        declared = headers.get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_body_bytes:
            await self._reject(send)
            return
        path = scope.get("path", "")
        api_path = path.startswith("/api/")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in SECURITY_HEADERS if k not in existing]
                if api_path and b"cache-control" not in existing:
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = [*message.get("headers", []), *extra]
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _reject(self, send):
        body = json.dumps({"detail": "Request body too large"}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *SECURITY_HEADERS]})
        await send({"type": "http.response.body", "body": body})
