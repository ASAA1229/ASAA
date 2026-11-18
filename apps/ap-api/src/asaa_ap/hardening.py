"""Baseline HTTP hardening: security response headers and a request body size limit (pure ASGI)."""
from __future__ import annotations

import json

from starlette.exceptions import HTTPException

MAX_BODY_BYTES = 1_048_576  # 1 MiB; JSON APIs here carry small payloads. Document upload will need its own limit.
# Tighter limits for specific write paths (method POST/PUT/PATCH). The event envelope plus a 16 KiB data object fits in 32 KiB.
PATH_LIMITS = {"/api/v1/integration/events": 32 * 1024}

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]


class BodyTooLarge(HTTPException):
    """Raised from the receive wrapper once the streamed request body passes the limit (with or without Content-Length).
    An HTTPException so FastAPI's body parsing re-raises it as a 413 instead of masking it as a generic 400."""

    def __init__(self):
        super().__init__(status_code=413, detail="Request body too large")


class HardeningMiddleware:
    def __init__(self, app, max_body_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k: v for k, v in scope["headers"]}
        path = scope.get("path", "")
        limit = min(self.max_body_bytes, PATH_LIMITS.get(path, self.max_body_bytes)) if scope.get("method") in {"POST", "PUT", "PATCH"} else self.max_body_bytes
        declared = headers.get(b"content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._reject(send)
            return
        api_path = path.startswith("/api/")

        started = False
        received = 0

        async def receive_wrapper():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLarge
            return message

        async def send_wrapper(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in SECURITY_HEADERS if k not in existing]
                if api_path and b"cache-control" not in existing:
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = [*message.get("headers", []), *extra]
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except BodyTooLarge:
            if started:  # the response is already under way: cannot change it, drop the connection
                raise
            await self._reject(send)

    async def _reject(self, send):
        body = json.dumps({"detail": "Request body too large"}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *SECURITY_HEADERS]})
        await send({"type": "http.response.body", "body": body})
