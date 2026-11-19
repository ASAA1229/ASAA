"""ASGI hardening: request bodies are counted as they stream (with or without Content-Length), tighter limit for event ingest."""
import asyncio
import json

import pytest

from asaa_ap.hardening import HardeningMiddleware
from tests.integration_support import URL, as_producer, integration_settings  # noqa: F401

HEADERS = {"Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def writer(client):
    as_producer(client)


def run_asgi(app, body_chunks, headers=None, path="/api/v1/integration/events", method="POST"):
    """Drive a pure ASGI app with chunked request messages and capture what it sends."""
    sent, consumed = [], []
    chunks = list(body_chunks)

    async def receive():
        if chunks:
            data = chunks.pop(0)
            consumed.append(len(data))
            return {"type": "http.request", "body": data, "more_body": bool(chunks)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": method, "path": path, "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]}
    asyncio.run(app(scope, receive, send))
    return sent, consumed


async def echo_length_app(scope, receive, send):
    total = 0
    while True:
        message = await receive()
        total += len(message.get("body", b""))
        if not message.get("more_body"):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(total).encode()})


def test_streamed_bodies_are_limited_without_content_length():
    app = HardeningMiddleware(echo_length_app)
    chunk = b"x" * 8192
    sent, consumed = run_asgi(app, [chunk] * 10)  # 80 KiB, no Content-Length, events path (limit 32 KiB)
    assert sent[0]["status"] == 413 and json.loads(sent[1]["body"])["detail"] == "Request body too large"
    assert sum(consumed) <= 40 * 1024  # stopped reading soon after the limit instead of buffering everything
    sent, _ = run_asgi(app, [chunk] * 2)  # 16 KiB is fine on the events path
    assert sent[0]["status"] == 200 and sent[1]["body"] == b"16384"
    sent, _ = run_asgi(app, [chunk] * 140, path="/api/v1/ap/suppliers")  # default limit 1 MiB
    assert sent[0]["status"] == 413
    sent, _ = run_asgi(app, [chunk] * 100, path="/api/v1/ap/suppliers")
    assert sent[0]["status"] == 200


def test_a_lying_content_length_cannot_bypass_the_limit():
    app = HardeningMiddleware(echo_length_app)
    sent, _ = run_asgi(app, [b"x" * 8192] * 10, headers={"content-length": "10"})
    assert sent[0]["status"] == 413


def test_declared_oversized_bodies_are_rejected_up_front_and_get_requests_are_unaffected():
    app = HardeningMiddleware(echo_length_app)
    sent, consumed = run_asgi(app, [b"x"], headers={"content-length": str(33 * 1024)})
    assert sent[0]["status"] == 413 and consumed == []
    sent, _ = run_asgi(app, [b""], method="GET")
    assert sent[0]["status"] == 200


def test_the_events_endpoint_rejects_an_oversized_chunked_upload(client):
    def chunks():
        for _ in range(10):
            yield b"x" * 8192

    response = client.post(URL, content=chunks(), headers=HEADERS)
    assert response.status_code == 413
    assert client.get(URL).json() == []


def test_security_headers_are_present_on_the_413(client):
    response = client.post(URL, content=b"x" * (40 * 1024), headers=HEADERS)
    assert response.status_code == 413 and response.headers["x-content-type-options"] == "nosniff"


