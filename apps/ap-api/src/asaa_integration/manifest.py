"""GET /.well-known/asaa-service: unauthenticated, secret-free self-description (asaa.service-manifest.v1)."""
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from asaa_ap.config import get_settings
from asaa_ap.database import engine

SERVICE_ID = "asaa-api"
PROJECT = "ASAA"
API_VERSION = "0.4.0"  # keep equal to the FastAPI app version in asaa_ap.main
CAPABILITIES = ["organization", "governance", "events.ingest", "ecosystem.status"]
CONTRACTS = {"serviceManifest": "v1", "eventEnvelope": "v1"}
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")

router = APIRouter(tags=["Operations"])


@lru_cache(maxsize=1)
def migration_head() -> str | None:
    """Head revision from the migration scripts, or None when the scripts are not shipped next to the package."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        for base in (Path(__file__).resolve().parents[2], Path.cwd()):
            ini = base / "alembic.ini"
            if ini.is_file():
                config = Config(str(ini))
                config.set_main_option("script_location", str(base / "migrations"))
                return ScriptDirectory.from_config(config).get_current_head()
    except Exception:  # noqa: BLE001 - a manifest must never fail because alembic is unavailable
        return None
    return None


def check_database() -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except SQLAlchemyError:
        return "down"


def check_migrations() -> str:
    try:
        with engine.connect() as connection:
            row = connection.execute(text("SELECT version_num FROM alembic_version")).first()
    except SQLAlchemyError:
        return "degraded"  # no migration history (unreachable database is reported by the database check)
    if row is None:
        return "degraded"
    head = migration_head()
    if head is None:
        return "ok"  # history exists; the head cannot be determined without the migration scripts
    return "ok" if row[0] == head else "degraded"


def build_manifest() -> dict:
    settings = get_settings()
    checks = {"database": check_database()}
    checks["migrations"] = check_migrations() if checks["database"] == "ok" else "down"
    if "down" in checks.values():
        status = "down" if checks["database"] == "down" else "degraded"
    elif "degraded" in checks.values():
        status = "degraded"
    else:
        status = "ok"
    commit = (settings.build_commit or "").lower()
    return {
        "schema": "asaa.service-manifest.v1",
        "service": SERVICE_ID,
        "project": PROJECT,
        "version": API_VERSION,
        "commit": commit if _COMMIT.match(commit) else None,
        "environment": settings.environment,
        "status": status,
        "checkedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "checks": checks,
        "capabilities": list(CAPABILITIES),
        "contracts": dict(CONTRACTS),
    }


@router.get("/.well-known/asaa-service", include_in_schema=True)
def service_manifest(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return build_manifest()
