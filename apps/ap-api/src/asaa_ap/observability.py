"""Structured JSON logging with request IDs and redaction, plus basic Prometheus-style metrics.

Provider independent: logs go to stdout as one JSON object per line so any collector
(hosting platform, Loki, ELK, CloudWatch agent...) can ship them. No external service is
configured here.
"""
from __future__ import annotations

import contextvars
import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict

REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("asaa_request_id", default=None)
REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|"
    r"bank|account[_-]?number|iban|ifsc|ssn|tax[_-]?id|pan|aadhaar|salary|gross|net_amount|"
    r"deduction|breakdown|email|phone|dob|birth|address)", re.I)
_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I), "Bearer " + REDACTED),
    (re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), REDACTED),  # JWT
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), REDACTED),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), REDACTED),  # e-mail address
    (re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)[^@\s]+(@)", re.I), r"\1" + REDACTED + r"\2"),  # URL password
    (re.compile(r"(?i)([\w-]*(?:password|passwd|secret|token|api[_-]?key|code)[\w-]*)\s*[=:]\s*[^\s&\"']+"), r"\1=" + REDACTED),
]


def redact(value, key: str | None = None, _depth: int = 0):
    """Return a copy of value with secrets and personal data masked (by key name and by value pattern)."""
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if _depth > 6:
        return REDACTED
    if isinstance(value, str):
        for pattern, replacement in _PATTERNS:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, dict):
        return {str(k): redact(v, str(k), _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(v, None, _depth + 1) for v in value]
    return value


_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": REQUEST_ID.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                entry[key] = redact(value, key)
        if record.exc_info:
            # Exception type and a redacted message only; stack frames may contain local data.
            exc_type, exc, _ = record.exc_info
            entry["exception"] = {"type": exc_type.__name__, "message": redact(str(exc))}
        return json.dumps(entry, default=str, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not any(getattr(h, "_asaa_json", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._asaa_json = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level.upper())


class Metrics:
    """Tiny thread-safe in-process metrics registry rendered in Prometheus text format."""
    BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.requests = defaultdict(int)
            self.duration_sum = defaultdict(float)
            self.duration_count = defaultdict(int)
            self.buckets = defaultdict(int)
            self.in_flight = 0
            self.started = time.time()

    def begin(self):
        with self._lock:
            self.in_flight += 1

    def observe(self, method: str, route: str, status: int, seconds: float):
        with self._lock:
            self.in_flight -= 1
            self.requests[(method, route, status)] += 1
            self.duration_sum[(method, route)] += seconds
            self.duration_count[(method, route)] += 1
            for bound in self.BUCKETS:
                if seconds <= bound:
                    self.buckets[(method, route, bound)] += 1

    def render(self) -> str:
        lines = ["# TYPE asaa_http_requests_total counter"]
        with self._lock:
            for (method, route, status), count in sorted(self.requests.items()):
                lines.append(f'asaa_http_requests_total{{method="{method}",route="{route}",status="{status}"}} {count}')
            lines.append("# TYPE asaa_http_request_duration_seconds histogram")
            for (method, route), total in sorted(self.duration_sum.items()):
                for bound in self.BUCKETS:
                    lines.append(f'asaa_http_request_duration_seconds_bucket{{method="{method}",route="{route}",le="{bound}"}} {self.buckets.get((method, route, bound), 0)}')
                count = self.duration_count[(method, route)]
                lines.append(f'asaa_http_request_duration_seconds_bucket{{method="{method}",route="{route}",le="+Inf"}} {count}')
                lines.append(f'asaa_http_request_duration_seconds_sum{{method="{method}",route="{route}"}} {total:.6f}')
                lines.append(f'asaa_http_request_duration_seconds_count{{method="{method}",route="{route}"}} {count}')
            lines.append("# TYPE asaa_http_requests_in_flight gauge")
            lines.append(f"asaa_http_requests_in_flight {self.in_flight}")
            lines.append("# TYPE asaa_process_uptime_seconds gauge")
            lines.append(f"asaa_process_uptime_seconds {time.time() - self.started:.0f}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UUID_SEGMENT = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}(?=/|$)")
_log = logging.getLogger("asaa.request")


def route_label(scope) -> str:
    """Low-cardinality route label: the route template when known, else the path with ids collapsed."""
    route = scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return template
    return _UUID_SEGMENT.sub("/{id}", scope.get("path", ""))


class RequestContextMiddleware:
    """Pure-ASGI middleware: request ID, access log (no query string, no bodies, no headers), metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        supplied = headers.get("x-request-id") or headers.get("x-correlation-id")
        request_id = supplied if supplied and _SAFE_ID.match(supplied) else uuid.uuid4().hex
        token = REQUEST_ID.set(request_id)
        started = time.perf_counter()
        status = {"code": 500}
        metrics.begin()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            _log.error("unhandled_exception", extra={"method": scope["method"], "path": scope["path"]}, exc_info=exc)
            raise
        finally:
            elapsed = time.perf_counter() - started
            label = route_label(scope)
            metrics.observe(scope["method"], label, status["code"], elapsed)
            if scope["path"] not in {"/health", "/metrics"}:
                _log.info("request", extra={
                    "method": scope["method"], "path": _UUID_SEGMENT.sub("/{id}", scope["path"]),
                    "status": status["code"], "duration_ms": round(elapsed * 1000, 2),
                })
            REQUEST_ID.reset(token)
