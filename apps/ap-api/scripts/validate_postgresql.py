"""Validate a provisioned PostgreSQL production database without exposing credentials."""

from pathlib import Path
import json
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from asaa_ap.config import get_settings
from asaa_ap.database import Base, engine
from asaa_ap import models as ap_models  # noqa: F401
from asaa_ap import procurement_models as procurement_models  # noqa: F401
from asaa_people import models as people_models  # noqa: F401
from asaa_governance import models as governance_models  # noqa: F401
from asaa_governance import authority as authority_models  # noqa: F401
from asaa_governance import administration as administration_models  # noqa: F401
from asaa_governance import authorization as authorization_models  # noqa: F401
from asaa_workforce_finance import models as workforce_models  # noqa: F401


def main() -> int:
    settings = get_settings()
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    record(
        "production_environment",
        settings.environment == "production",
        "ASAA_AP_ENVIRONMENT must be production",
    )
    record(
        "postgresql_dialect",
        engine.dialect.name == "postgresql",
        "Configured SQLAlchemy dialect must be PostgreSQL",
    )
    if settings.environment != "production" or engine.dialect.name != "postgresql":
        print(json.dumps({"status": "failed", "checks": checks}, indent=2))
        return 1

    root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(root / "migrations"))
    expected_revision = ScriptDirectory.from_config(alembic_config).get_current_head()

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            server_version = int(connection.scalar(text("SHOW server_version_num")))
            record(
                "postgresql_version",
                server_version >= 160000,
                f"PostgreSQL server version number: {server_version}",
            )

            ssl_enabled = bool(connection.scalar(text(
                "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
            )))
            record("tls_encryption", ssl_enabled, "Current database connection must use TLS")

            role = connection.execute(text("""
                SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
                FROM pg_roles WHERE rolname = current_user
            """)).one_or_none()
            role_is_restricted = role is not None and not any(bool(value) for value in role)
            record(
                "application_role_least_privilege",
                role_is_restricted,
                "Connected role must not be superuser, create roles/databases, replicate or bypass RLS",
            )
            schema_create = bool(connection.scalar(text(
                "SELECT has_schema_privilege(current_user, current_schema(), 'CREATE')"
            )))
            record(
                "application_role_schema_ownership",
                not schema_create,
                "Runtime application role must not have schema CREATE privilege",
            )

            current_revision = MigrationContext.configure(connection).get_current_revision()
            record(
                "migration_head",
                current_revision == expected_revision,
                f"Database revision: {current_revision}; code head: {expected_revision}",
            )

            inspector = inspect(connection)
            columns = inspector.get_columns("alembic_version") if inspector.has_table("alembic_version") else []
            version_column = next((column for column in columns if column["name"] == "version_num"), None)
            version_length = getattr(version_column["type"], "length", 0) if version_column else 0
            record(
                "migration_revision_capacity",
                bool(version_length and version_length >= 128),
                f"alembic_version.version_num length: {version_length}",
            )

            existing_tables = set(inspector.get_table_names())
            expected_tables = set(Base.metadata.tables)
            owned_tables = connection.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tableowner = current_user"
            )).scalars().all()
            owned_application_tables = sorted(set(owned_tables) & expected_tables)
            record(
                "application_role_table_ownership",
                not owned_application_tables,
                "Runtime role does not own application tables"
                if not owned_application_tables else "Runtime role owns tables: " + ", ".join(owned_application_tables),
            )
            missing_tables = sorted(expected_tables - existing_tables)
            record(
                "application_schema",
                not missing_tables,
                "All application model tables exist" if not missing_tables else "Missing tables: " + ", ".join(missing_tables),
            )

            missing_privileges = []
            for table_name in sorted(expected_tables & existing_tables):
                for privilege in ("SELECT", "INSERT", "UPDATE"):
                    allowed = connection.scalar(text(
                        "SELECT has_table_privilege(current_user, :table_name, :privilege)"
                    ), {"table_name": table_name, "privilege": privilege})
                    if not allowed:
                        missing_privileges.append(f"{table_name}:{privilege}")
            record(
                "application_table_privileges",
                not missing_privileges,
                "Required SELECT/INSERT/UPDATE privileges are present"
                if not missing_privileges else "Missing privileges: " + ", ".join(missing_privileges),
            )
    except SQLAlchemyError:
        record(
            "database_connection",
            False,
            "Database validation failed; inspect protected server logs without exposing credentials",
        )

    failed = [item for item in checks if not item["passed"]]
    print(json.dumps({
        "status": "passed" if not failed else "failed",
        "database_url": "redacted",
        "checks": checks,
    }, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
