"""Retention purge script, seed script credential refusal and migration 0021 (composite event key, declared severity)."""
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from asaa_ap.database import Base
from asaa_ap.models import AuditEvent
from asaa_integration.models import IntegrationEvent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import purge_integration_events as purge_script  # noqa: E402
import seed_ecosystem_projects as seed_script  # noqa: E402

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'purge.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


def add_event(session, org, age_days, event_id=None):
    session.add(IntegrationEvent(id=event_id or f"e-{org}-{age_days}-{len(session.new)}", organization_id=org, source="jarvis", type="jarvis.task.done",
                                 project="JARVIS", severity="info", declared_severity="info", occurred_at=NOW - timedelta(days=age_days),
                                 received_at=NOW - timedelta(days=age_days), data={"marker": "keep-out-of-audit"}, received_by="svc"))


def test_purge_removes_only_events_past_retention_and_audits_counts(session):
    for age in (1, 100, 179):
        add_event(session, "org-a", age)
    for age in (181, 400):
        add_event(session, "org-a", age)
    add_event(session, "org-b", 500)
    session.commit()
    counts = purge_script.purge(session, 180, now=NOW)
    assert counts == {"org-a": 2, "org-b": 1}
    assert sorted(e.received_at.replace(tzinfo=timezone.utc) >= NOW - timedelta(days=180) for e in session.scalars(select(IntegrationEvent))) == [True] * 3
    audits = session.scalars(select(AuditEvent).where(AuditEvent.action == "integration_event.purged").order_by(AuditEvent.organization_id)).all()
    assert [(a.organization_id, a.details["rows"], a.details["retention_days"]) for a in audits] == [("org-a", 2, 180), ("org-b", 1, 180)]
    assert all("marker" not in str(a.details) for a in audits) and audits[0].actor_id == "system:integration-retention"


def test_purge_is_idempotent_and_dry_run_changes_nothing(session):
    add_event(session, "org-a", 200)
    session.commit()
    assert purge_script.purge(session, 180, now=NOW, dry_run=True) == {"org-a": 1}
    assert session.scalars(select(IntegrationEvent)).all() and not session.scalars(select(AuditEvent)).all()
    assert purge_script.purge(session, 180, now=NOW) == {"org-a": 1}
    assert purge_script.purge(session, 180, now=NOW) == {}
    assert len(session.scalars(select(AuditEvent)).all()) == 1


def test_purge_rejects_a_retention_below_one_day(session):
    with pytest.raises(ValueError):
        purge_script.purge(session, 0, now=NOW)


def test_purge_cli_uses_the_configured_default_and_the_given_database(tmp_path, capsys):
    db = tmp_path / "cli.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        add_event(s, "org-a", 0)
        old = datetime.now(timezone.utc) - timedelta(days=400)
        s.add(IntegrationEvent(id="old", organization_id="org-a", source="jarvis", type="jarvis.task.done", project="JARVIS", severity="info",
                               declared_severity="info", occurred_at=old, received_at=old, data={}, received_by="svc"))
        s.commit()
    engine.dispose()
    assert purge_script.main(["--database-url", f"sqlite:///{db}", "--dry-run"]) == 0
    assert "[dry run] would remove 1 event(s) older than 180 day(s)" in capsys.readouterr().out
    assert purge_script.main(["--database-url", f"sqlite:///{db}", "--days", "30"]) == 0
    assert "removed 1 event(s) older than 30 day(s)" in capsys.readouterr().out


def test_default_retention_is_a_documented_placeholder_pending_owner_approval():
    from asaa_ap.config import Settings
    assert Settings().integration_event_retention_days == 180
    assert "PENDING OWNER APPROVAL" in (ROOT / "src" / "asaa_ap" / "config.py").read_text()


@pytest.mark.parametrize("script", [purge_script, seed_script])
@pytest.mark.parametrize("url", ["postgresql+psycopg://user:s3cret@db:5432/asaa", "postgresql://user:s3cret@db/asaa"])
def test_scripts_refuse_database_urls_with_embedded_passwords(script, url, capsys):
    assert script.main(["--database-url", url]) == 2
    captured = capsys.readouterr()
    assert "s3cret" not in captured.out + captured.err and "password" in captured.err.lower()


def test_scripts_accept_password_free_urls_syntactically(tmp_path):
    db = tmp_path / "ok.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    assert purge_script.main(["--database-url", f"sqlite:///{db}"]) == 0
    assert seed_script.main(["--org-id", "o", "--database-url", f"sqlite:///{db}", "--dry-run"]) == 0


# ------------------------------------------------------------------------------------ migration 0021

def alembic(db, *args):
    env = {**os.environ, "ASAA_AP_DATABASE_URL": f"sqlite:///{db}"}
    result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1500:]
    return result


def table_info(db):
    con = sqlite3.connect(db)
    try:
        return {row[1]: row[5] for row in con.execute("PRAGMA table_info(integration_events)")}
    finally:
        con.close()


def test_migration_0021_scopes_ids_per_org_keeps_data_and_downgrades(tmp_path):
    db = tmp_path / "mig.db"
    alembic(db, "upgrade", "0020_integration_events")
    assert table_info(db)["id"] == 1 and "declared_severity" not in table_info(db) and table_info(db)["organization_id"] == 0
    con = sqlite3.connect(db)
    con.execute("INSERT INTO integration_events VALUES ('11111111-1111-1111-1111-111111111111','org-a','jarvis','jarvis.task.done','JARVIS',"
                "NULL,NULL,'warning','2026-11-18 10:00:00','2026-11-18 10:00:01','{\"k\": 1}','svc')")
    con.commit()
    con.close()
    alembic(db, "upgrade", "head")
    info = table_info(db)
    assert info["id"] == 1 and info["organization_id"] == 2 and "declared_severity" in info  # composite primary key (id, organization_id)
    con = sqlite3.connect(db)
    assert con.execute("SELECT id, organization_id, severity, declared_severity, data FROM integration_events").fetchall() == [
        ("11111111-1111-1111-1111-111111111111", "org-a", "warning", "warning", '{"k": 1}')]
    con.execute("INSERT INTO integration_events (id, organization_id, source, type, project, severity, declared_severity, occurred_at, received_at, data, received_by)"
                " VALUES ('11111111-1111-1111-1111-111111111111','org-b','jarvis','jarvis.task.done','JARVIS','info','info','2026-11-18','2026-11-18','{}','svc')")
    con.commit()  # the same id under another organization is allowed now
    indexes = {row[1] for row in con.execute("PRAGMA index_list(integration_events)")}
    con.close()
    assert {"ix_integration_events_org_occurred", "ix_integration_events_source", "ix_integration_events_type"} <= indexes
    con = sqlite3.connect(db)
    con.execute("DELETE FROM integration_events WHERE organization_id = 'org-b'")
    con.commit()
    con.close()
    alembic(db, "downgrade", "-1")
    info = table_info(db)
    assert info["id"] == 1 and info["organization_id"] == 0 and "declared_severity" not in info
    con = sqlite3.connect(db)
    assert con.execute("SELECT id, severity FROM integration_events").fetchall() == [("11111111-1111-1111-1111-111111111111", "warning")]
    con.close()
    alembic(db, "upgrade", "head")
    assert "declared_severity" in table_info(db)
