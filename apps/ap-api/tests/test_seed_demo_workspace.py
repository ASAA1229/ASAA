"""Demo workspace seed (E3:D3.23): idempotent, refuses outside development/test, and fills every workspace table."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from asaa_ap.database import Base
from asaa_ap.models import AuditEvent
from asaa_workforce_finance.models import ExpenseClaim, Timesheet

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seed_demo_workspace as demo  # noqa: E402

ORG = "asaa"


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


def test_seed_is_idempotent_and_fills_every_workspace(session):
    first = demo.seed_demo(session, ORG)
    second = demo.seed_demo(session, ORG)
    assert first == second
    empty = [name for name, count in first.items() if count == 0]
    assert not empty, f"workspace tables left empty: {empty}"


def test_some_timesheets_and_expenses_are_submitted_and_labelled(session):
    demo.seed_demo(session, ORG)
    for model in (Timesheet, ExpenseClaim):
        assert session.scalar(select(func.count()).select_from(model).where(model.organization_id == ORG, model.status == "Submitted")) >= 1
    assert all(e.details.get("data_class") == "TEMPORARY_TEST_DATA" for e in session.scalars(select(AuditEvent).where(AuditEvent.action.like("%submitted"))) if e.entity_id.startswith("fx-demo"))


def test_budget_variance_inputs_exist(session):
    demo.seed_demo(session, ORG)
    counts = demo.table_counts(session, ORG)
    assert counts["budget_lines"] >= 1 and counts["scenarios"] >= 1 and counts["governed_records"] > 40


def test_refuses_in_production():
    with pytest.raises(SystemExit):
        demo.refuse_unless_dev(SimpleNamespace(environment="production"))
    demo.refuse_unless_dev(SimpleNamespace(environment="development"))
    demo.refuse_unless_dev(SimpleNamespace(environment="test"))


def test_main_refuses_when_environment_is_not_development(monkeypatch):
    monkeypatch.setattr("asaa_ap.config.get_settings", lambda: SimpleNamespace(environment="staging"))
    with pytest.raises(SystemExit):
        demo.main()
