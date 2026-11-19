"""Read-only operational status for the portal: backup freshness and platform configuration flags (no secrets)."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from asaa_ap.config import get_settings
from asaa_ap.database import get_db
from asaa_ap.security import Principal, require_permission

router = APIRouter(prefix="/api/v1/operations", tags=["Operations"])


@router.get("/backup-status")
def backup_status(principal: Annotated[Principal, Depends(require_permission("ops:backup:read"))]):
    """Mirrors scripts/backup_restore.py check-staleness using the status file written by `backup_restore.py scheduled`."""
    settings = get_settings()
    if not settings.backup_dir:
        return {"configured": False, "ok": False, "reason": "ASAA_AP_BACKUP_DIR is not set; no backup status is available."}
    directory = Path(settings.backup_dir)
    status_file = directory / "backup-status.json"
    if not status_file.exists():
        return {"configured": True, "ok": False, "reason": "no backup status recorded"}
    status = json.loads(status_file.read_text())
    result = {"configured": True, "ok": False, "reason": None, "last_success_at": status.get("last_success_at"), "last_failure_at": status.get("last_failure_at"),
              "last_artifact": status.get("last_artifact"), "age_hours": None, "limit_hours": settings.backup_max_age_hours, "retention": status.get("retention")}
    if not status.get("last_success_at"):
        result["reason"] = "no successful backup recorded"
        return result
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(status["last_success_at"])).total_seconds() / 3600
    result["age_hours"] = round(age, 2)
    if status.get("last_failure_at") and status["last_failure_at"] > status["last_success_at"]:
        result["reason"] = "last backup run failed"
    elif age > settings.backup_max_age_hours:
        result["reason"] = f"newest backup is {age:.1f}h old"
    elif not (directory / status.get("last_artifact", "")).exists():
        result["reason"] = "recorded backup artifact is missing"
    else:
        result["ok"] = True
    return result


@router.get("/status")
def platform_status(db: Annotated[Session, Depends(get_db)], principal: Annotated[Principal, Depends(require_permission("ops:status:read"))]):
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "available"
    except SQLAlchemyError:
        database = "unavailable"
    return {"environment": settings.environment, "database": database, "database_dialect": db.bind.dialect.name if db.bind else None,
            "identity_provider": settings.identity_provider, "notification_provider": settings.notification_provider,
            "backup_configured": bool(settings.backup_dir), "oidc_issuer_configured": bool(settings.jwt_issuer),
            "jwks_configured": bool(settings.jwt_jwks_url), "required_acr_configured": bool(settings.required_acr), "required_amr_configured": bool(settings.required_amr)}
