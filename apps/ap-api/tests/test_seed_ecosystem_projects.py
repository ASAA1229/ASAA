"""Seed script for the four ecosystem project register records: idempotent, org-scoped, valid against the register catalogue."""
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from asaa_ap.database import Base
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from asaa_registers.models import GovernedRecord

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import seed_ecosystem_projects as seed_script  # noqa: E402

REGISTRY = json.loads(seed_script.DEFAULT_REGISTRY.read_text())


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


def projects(session, org):
    return session.scalars(select(GovernedRecord).where(GovernedRecord.organization_id == org, GovernedRecord.register_type == "project")
                           .order_by(GovernedRecord.code)).all()


def test_creates_the_four_projects_with_registry_data(session):
    result = seed_script.seed(session, "asaa", REGISTRY)
    assert result == {"created": ["ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"], "skipped": []}
    rows = {r.code: r for r in projects(session, "asaa")}
    assert set(rows) == {"ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"}
    assert rows["TEMPLATES"].data == {"project_status": "Active", "classification": "Professional", "repository_url": "https://github.com/ASAA1229/Templates"}
    assert rows["PORTFOLIO"].data["repository_url"] == "https://github.com/ASAA1229/Portfolio"
    assert all(r.status == "Draft" and r.revision == 1 and r.owner_subject == "system:ecosystem-seed" and len(r.id) == 36 for r in rows.values())
    assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "register_record.seeded")) == 4


def test_is_idempotent_and_keeps_existing_records_untouched(session):
    seed_script.seed(session, "asaa", REGISTRY)
    before = {r.code: (r.id, r.version) for r in projects(session, "asaa")}
    again = seed_script.seed(session, "asaa", REGISTRY)
    assert again == {"created": [], "skipped": ["ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"]}
    assert {r.code: (r.id, r.version) for r in projects(session, "asaa")} == before
    assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "register_record.seeded")) == 4


def test_only_missing_projects_are_created_and_other_orgs_are_independent(session):
    seed_script.seed(session, "asaa", {**REGISTRY, "projects": [p for p in REGISTRY["projects"] if p["code"] == "ASAA"]})
    result = seed_script.seed(session, "asaa", REGISTRY)
    assert result["skipped"] == ["ASAA"] and result["created"] == ["JARVIS", "TEMPLATES", "PORTFOLIO"]
    other = seed_script.seed(session, "other-org", REGISTRY)
    assert len(other["created"]) == 4 and len(projects(session, "other-org")) == 4 and len(projects(session, "asaa")) == 4


def test_dry_run_writes_nothing(session):
    assert seed_script.seed(session, "asaa", REGISTRY, dry_run=True)["created"] == ["ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"]
    assert projects(session, "asaa") == []


def test_cli_creates_records_in_the_given_database_and_rerun_is_a_noop(tmp_path, capsys):
    db = tmp_path / "cli.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    args = ["--org-id", "asaa", "--database-url", f"sqlite:///{db}"]
    assert seed_script.main(args) == 0
    assert "created: ASAA, JARVIS, TEMPLATES, PORTFOLIO" in capsys.readouterr().out
    assert seed_script.main(args) == 0
    assert "created: -" in capsys.readouterr().out
    assert seed_script.main(args + ["--registry", str(tmp_path / "missing.json")]) == 2


def test_seeded_projects_are_visible_through_the_register_api_with_the_new_fields(client):
    from asaa_ap.database import get_db
    session = next(client.app.dependency_overrides[get_db]())
    seed_script.seed(session, "org-a", REGISTRY)
    client.app.dependency_overrides[get_principal] = lambda: Principal("reader", "org-a", frozenset({"register:project:read"}))
    listed = client.get("/api/v1/registers/project").json()
    assert [r["code"] for r in listed] == ["ASAA", "JARVIS", "PORTFOLIO", "TEMPLATES"]
    assert all(r["data"]["classification"] == "Professional" for r in listed)
    client.app.dependency_overrides[get_principal] = lambda: Principal("reader", "org-b", frozenset({"register:project:read"}))
    assert client.get("/api/v1/registers/project").json() == []
