"""Least-privilege PostgreSQL roles (ASAA-004). Needs ASAA_AP_POSTGRES_TEST_URL for a role allowed to create
databases and roles (a disposable local/CI server only)."""
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import db_roles  # noqa: E402
import load_test  # noqa: E402

PG_URL = os.getenv("ASAA_AP_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="needs ASAA_AP_POSTGRES_TEST_URL")


def alembic(url, *args):
    env = {**os.environ, "ASAA_AP_DATABASE_URL": url, "ASAA_AP_ENVIRONMENT": "test"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)


@pytest.fixture
def separated_database(monkeypatch):
    parsed = urlparse(PG_URL.replace("postgresql+psycopg://", "postgresql://", 1))
    host, port = parsed.hostname, parsed.port or 5432
    suffix = uuid.uuid4().hex[:8]
    dbname, migrator, runtime = f"asaa_priv_{suffix}", f"mig_{suffix}", f"run_{suffix}"
    mig_pw, run_pw = "Mig-" + uuid.uuid4().hex, "Run-" + uuid.uuid4().hex
    monkeypatch.setenv("ASAA_DB_MIGRATOR_PASSWORD", mig_pw)
    monkeypatch.setenv("ASAA_DB_RUNTIME_PASSWORD", run_pw)
    admin = psycopg.connect(host=host, port=port, user=parsed.username, password=parsed.password, dbname=parsed.path.lstrip("/"), autocommit=True)
    admin.execute(f'CREATE DATABASE "{dbname}"')
    admin_url = f"postgresql+psycopg://{parsed.username}:{parsed.password}@{host}:{port}/{dbname}"
    first = alembic(admin_url, "upgrade", "head")
    assert first.returncode == 0, first.stderr[-500:]
    db_roles.provision(admin_url, migrator, runtime)
    urls = {
        "admin": admin_url, "migrator_name": migrator, "runtime_name": runtime,
        "migrator": f"postgresql+psycopg://{migrator}:{mig_pw}@{host}:{port}/{dbname}",
        "runtime": f"postgresql+psycopg://{runtime}:{run_pw}@{host}:{port}/{dbname}",
    }
    yield urls
    admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    for role in (migrator, runtime):
        admin.execute(f'DROP ROLE IF EXISTS "{role}"')
    admin.close()


def test_runtime_role_passes_every_privilege_check(separated_database):
    result = db_roles.check(separated_database["runtime"])
    failed = [c for c in result["checks"] if not c["passed"]]
    assert failed == [] and result["status"] == "passed"
    names = {c["check"] for c in result["checks"]}
    assert {"alembic_version_update_denied", "alembic_version_write_attempt_refused", "create_table_refused",
            "drop_table_refused", "alter_table_refused", "truncate_refused", "audit_events_delete_attempt_refused"} <= names


def test_checker_detects_an_over_privileged_role(separated_database):
    """The owner/admin role must FAIL the runtime check, proving the checker is not vacuous."""
    result = db_roles.check(separated_database["admin"])
    assert result["status"] == "failed"
    assert any(not c["passed"] for c in result["checks"] if c["check"] in {"create_table_refused", "alembic_version_write_attempt_refused"})


def test_runtime_role_cannot_migrate_but_migration_role_can(separated_database):
    denied = alembic(separated_database["runtime"], "downgrade", "-1")
    assert denied.returncode != 0 and any(m in (denied.stderr + denied.stdout).lower() for m in ("permission denied", "must be owner", "insufficientprivilege"))
    ok_down = alembic(separated_database["migrator"], "downgrade", "-1")
    assert ok_down.returncode == 0, ok_down.stderr[-500:]
    ok_up = alembic(separated_database["migrator"], "upgrade", "head")
    assert ok_up.returncode == 0, ok_up.stderr[-500:]
    # a new migration creates tables owned by the migrator; re-provisioning keeps the runtime policy intact
    db_roles.provision(separated_database["admin"], separated_database["migrator_name"], separated_database["runtime_name"])
    assert db_roles.check(separated_database["runtime"])["status"] == "passed"


def test_application_works_end_to_end_as_the_runtime_role_and_audit_rows_are_append_only(separated_database, tmp_path):
    import asyncio
    process, base, token, _ = load_test.spawn_api(separated_database["runtime"], 1, tmp_path, migrate_url=separated_database["migrator"])
    try:
        result = asyncio.run(load_test.run_load(base, token, concurrency=4, duration=3, warmup=1))
    finally:
        process.terminate()
        process.wait(timeout=10)
    assert result["requests"] > 10 and result["error_rate"] == 0  # reads, creates and audit inserts all work with limited grants
    with psycopg.connect(separated_database["runtime"].replace("postgresql+psycopg://", "postgresql://", 1)) as db:
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] > 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE audit_events SET action = 'tampered'")
