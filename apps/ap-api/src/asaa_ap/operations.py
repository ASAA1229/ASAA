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
              "last_artifact": status.get("last_artifact"), "age_hours": None, "limit_hours": settings.backup_max_age_hours, "retention": status.get("retention"),
              "restore_test": {"last_at": status.get("last_restore_test_at"), "ok": status.get("last_restore_test_ok"), "artifact": status.get("last_restore_test_artifact"),
                               "observed_restore_seconds": status.get("last_restore_test_seconds"), "rows_verified": status.get("last_restore_test_rows"),
                               "error": status.get("last_restore_test_error"),
                               "note": "Observation only. RPO/RTO targets and the restore-test cadence are owner decisions and are not enforced here."}}
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


def _migration_heads() -> list[str] | None:
    """Alembic head revision(s) shipped with this build, or None when the migration scripts are not packaged with the runtime."""
    directory = Path(__file__).resolve().parents[2] / "migrations"
    if not directory.is_dir():
        return None
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config()
    config.set_main_option("script_location", str(directory))
    return sorted(ScriptDirectory.from_config(config).get_heads())


@router.get("/deployment")
def deployment_status(db: Annotated[Session, Depends(get_db)], principal: Annotated[Principal, Depends(require_permission("ops:status:read"))]):
    """Deployment-management view: application version, schema revision applied to the database versus the revision this build expects, and
    non-secret effective configuration. Secrets (keys, tokens, passwords, connection strings) are never returned."""
    from asaa_ap.main import app
    settings = get_settings()
    try:
        applied = sorted(row[0] for row in db.execute(text("SELECT version_num FROM alembic_version")).all())
    except SQLAlchemyError:
        db.rollback()
        applied = None
    expected = _migration_heads()
    schema = {"applied_revisions": applied, "expected_revisions": expected,
              "up_to_date": (applied == expected) if applied is not None and expected is not None else None,
              "note": "up_to_date is null when the schema was created without Alembic (development) or migration scripts are not packaged."}
    config = {"environment": settings.environment, "database_dialect": db.bind.dialect.name if db.bind else None, "identity_provider": settings.identity_provider,
              "notification_provider": settings.notification_provider, "log_level": settings.log_level, "cors_origin_count": len(settings.cors_origins),
              "api_docs_enabled": settings.environment != "production", "jwks_url_configured": bool(settings.jwt_jwks_url), "backup_max_age_hours": settings.backup_max_age_hours,
              "required_acr_configured": bool(settings.required_acr), "required_amr_configured": bool(settings.required_amr),
              "ap_match_tolerance_amount": str(settings.ap_match_tolerance_amount)}
    return {"application": {"name": settings.app_name, "version": app.version}, "schema": schema, "configuration": config, "generated_at": datetime.now(timezone.utc).isoformat()}
