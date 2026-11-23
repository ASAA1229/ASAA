import hmac
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from asaa_ap.api import router as ap_router
from asaa_ap.purchase_requests import router as purchase_requests_router
from asaa_ap.ar_api import router as ar_router
from asaa_ap.ar_credit import router as ar_credit_router
from asaa_ap.ar_adjustments import router as ar_adjustments_router
from asaa_people.api import hr_router, onboarding_router, payroll_router
from asaa_people.lifecycle import router as hr_lifecycle_router
from asaa_people.workflows import router as people_workflows_router
from asaa_people.payroll_rules import router as payroll_rules_router
from asaa_payables.api import router as payables_router
from asaa_attendance.api import router as attendance_router
from asaa_delivery.api import router as delivery_router
from asaa_ap.config import get_settings
from asaa_ap.database import engine
from asaa_ap.security import Principal, get_principal
from asaa_ap.hardening import HardeningMiddleware
from asaa_ap.observability import RequestContextMiddleware, configure_logging, metrics
from asaa_governance.api import router as master_data_router
from asaa_governance.authority import router as governance_router
from asaa_governance.administration import router as administration_router
from asaa_governance.authorization import router as authorization_router
from asaa_workforce_finance.api import router as workforce_finance_router
from asaa_identity.api import router as identity_sync_router
from asaa_notifications.api import router as notifications_router
from asaa_registers.api import router as registers_router
from asaa_reports.api import router as reports_router
from asaa_reports.lineage import router as report_lineage_router
from asaa_reports.analytics import router as report_analytics_router
from asaa_ap.operations import router as operations_router
from asaa_integration.manifest import router as manifest_router
from asaa_integration.events import router as integration_events_router
from asaa_integration.ecosystem import router as ecosystem_router
from asaa_people.leave_policy import router as leave_policy_router
from asaa_notifications.provider import InMemoryNotificationProvider, register_notification_provider
from asaa_identity.bootstrap import register_configured_providers

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("asaa.api")
# Interactive API docs and the OpenAPI document are disabled in production (docs/SECURITY.md section 8).
_production = settings.environment == "production"
app = FastAPI(title=settings.app_name, version="0.4.0",
              docs_url=None if _production else "/docs", redoc_url=None if _production else "/redoc",
              openapi_url=None if _production else "/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(HardeningMiddleware)
app.add_middleware(RequestContextMiddleware)
app.include_router(ap_router)
app.include_router(purchase_requests_router)
app.include_router(payables_router)
app.include_router(attendance_router)
app.include_router(delivery_router)
app.include_router(ar_router)
app.include_router(ar_credit_router)
app.include_router(ar_adjustments_router)
app.include_router(hr_router)
app.include_router(hr_lifecycle_router)
app.include_router(onboarding_router)
app.include_router(payroll_router)
app.include_router(people_workflows_router)
app.include_router(payroll_rules_router)
app.include_router(master_data_router)
app.include_router(governance_router)
app.include_router(administration_router)
app.include_router(authorization_router)
app.include_router(workforce_finance_router)
app.include_router(identity_sync_router)
app.include_router(notifications_router)
app.include_router(registers_router)
app.include_router(reports_router)
app.include_router(report_lineage_router)
app.include_router(report_analytics_router)
app.include_router(operations_router)
app.include_router(leave_policy_router)
app.include_router(manifest_router)
app.include_router(integration_events_router)
app.include_router(ecosystem_router)
if settings.notification_provider == "memory" and settings.environment != "production":
    register_notification_provider("memory", InMemoryNotificationProvider)
register_configured_providers(settings)


@app.get("/api/v1/me", tags=["Identity"])
def whoami(principal: Annotated[Principal, Depends(get_principal)]):
    """Verified session summary. Requires only a valid token; lets clients confirm a token is accepted."""
    return {"subject": principal.subject, "organization_id": principal.organization_id, "permissions": sorted(principal.permissions)}


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "asaa-enterprise-api"}


@app.get("/ready", tags=["Operations"])
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("readiness_check_failed", extra={"check": "database", "error_type": type(exc).__name__})
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ready", "database": "available"}


@app.get("/metrics", tags=["Operations"], include_in_schema=False)
def metrics_endpoint(authorization: Annotated[str | None, Header()] = None):
    configured = get_settings()
    token = configured.metrics_token
    if configured.environment == "production" and not token:
        raise HTTPException(status_code=404, detail="Not found")
    if token and not (authorization and hmac.compare_digest(authorization, f"Bearer {token}")):
        raise HTTPException(status_code=401, detail="Metrics token required", headers={"WWW-Authenticate": "Bearer"})
    return Response(metrics.render(), media_type="text/plain; version=0.0.4")
