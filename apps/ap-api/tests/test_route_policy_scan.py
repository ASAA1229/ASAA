"""Route-wide guard: every route requires a named permission (except a short allowlist) and every mutating route writes an audit record."""
import inspect

from fastapi.routing import APIRoute

from asaa_ap.main import app

PUBLIC = {"/health", "/ready", "/metrics", "/api/v1/me"}  # /metrics is bearer-token protected; /me only needs an authenticated principal


def _dependencies(dependant):
    for child in dependant.dependencies:
        yield child
        yield from _dependencies(child)


def _routes():
    return [r for r in app.routes if isinstance(r, APIRoute)]


def test_every_route_requires_a_named_permission_except_the_allowlist():
    missing = [r.path for r in _routes() if r.path not in PUBLIC
               and not any(getattr(d.call, "__qualname__", "").startswith("require_permission") for d in _dependencies(r.dependant))]
    assert missing == []


def test_every_mutating_route_writes_an_audit_record():
    unaudited = [f"{sorted(r.methods)} {r.path}" for r in _routes() if r.methods & {"POST", "PUT", "PATCH", "DELETE"}
                 and "audit" not in inspect.getsource(r.endpoint).lower()]
    assert unaudited == []
