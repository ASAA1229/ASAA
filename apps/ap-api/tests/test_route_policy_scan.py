"""Route-wide guard: every route requires a named permission (except a short allowlist) and every mutating route writes an audit record."""
import inspect

from fastapi.routing import APIRoute

from asaa_ap.main import app

PUBLIC = {"/health", "/ready", "/metrics", "/.well-known/asaa-service", "/api/v1/me"}  # /metrics is bearer-token protected; /me only needs an authenticated principal
# Authenticated-only routes that are scoped to the caller's own token subject or filter their sections by the caller's permissions.
SELF_SCOPED = {"/api/v1/notifications/preferences/me", "/api/v1/reports/summary"}
# Registers use a per-register permission factory (needs()) resolved from the path.
PER_REGISTER = "/api/v1/registers"
# Mutating routes whose audit record is written by the service layer they call (suppliers, AR, identity sync processing, notification processing).
SERVICE_AUDITED = {"/api/v1/ap/suppliers", "/api/v1/ap/suppliers/{supplier_id}", "/api/v1/ap/suppliers/{supplier_id}/status", "/api/v1/ar/customers",
                   "/api/v1/ar/invoices", "/api/v1/ar/invoices/{invoice_id}", "/api/v1/ar/invoices/{invoice_id}/issue", "/api/v1/ar/receipts",
                   "/api/v1/ar/receipts/{receipt_id}/allocations", "/api/v1/identity-sync/process", "/api/v1/identity-sync/reconcile",
                   "/api/v1/notifications/process"}


def _dependencies(dependant):
    for child in dependant.dependencies:
        yield child
        yield from _dependencies(child)


def _walk(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):  # FastAPI wraps included routers; flatten them or the scan sees nothing
            yield from _walk(route.original_router.routes)


def _routes():
    found = list(_walk(app.routes))
    assert len(found) > 150  # guards against the scan silently inspecting nothing
    return found


def test_every_route_requires_a_named_permission_except_the_allowlist():
    missing = [r.path for r in _routes() if r.path not in PUBLIC | SELF_SCOPED and not r.path.startswith(PER_REGISTER)
               and not any(getattr(d.call, "__qualname__", "").startswith("require_permission") for d in _dependencies(r.dependant))]
    assert missing == []


def test_every_mutating_route_writes_an_audit_record():
    unaudited = [f"{sorted(r.methods)} {r.path}" for r in _routes() if r.methods & {"POST", "PUT", "PATCH", "DELETE"}
                 and r.path not in SERVICE_AUDITED and "audit" not in inspect.getsource(r.endpoint).lower()]
    assert unaudited == []


def test_register_routes_resolve_a_per_register_permission():
    registers = [r for r in _routes() if r.path.startswith(PER_REGISTER) and r.path != PER_REGISTER + "/types"]
    assert registers and all(any(getattr(d.call, "__qualname__", "").startswith("needs") for d in _dependencies(r.dependant)) for r in registers)


def test_event_producer_service_accounts_cannot_use_business_routes(client, monkeypatch):
    from asaa_ap import security
    from asaa_ap.config import Settings
    from asaa_ap.security import Principal, get_principal
    monkeypatch.setattr(security, "get_settings", lambda: Settings(integration_producers={"jarvis-events": {"source": "jarvis", "project": "JARVIS", "typePrefix": "jarvis."}}))
    perms = frozenset({"ar:customer:read", "integration:event:read"})
    client.app.dependency_overrides[get_principal] = lambda: Principal("svc", "org-a", perms, "jarvis-events")
    assert client.get("/api/v1/ar/customers").status_code == 403
    assert client.get("/api/v1/integration/events").status_code == 200
    client.app.dependency_overrides[get_principal] = lambda: Principal("person", "org-a", perms, "portal-client")
    assert client.get("/api/v1/ar/customers").status_code == 200
