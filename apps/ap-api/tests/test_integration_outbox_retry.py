"""Failed ecosystem event staging leaves a durable retry marker; the sweep stages it later without touching business rows."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from asaa_ap.database import Base
from asaa_ap.models import AuditEvent
from asaa_integration import emitter, retry
from asaa_integration.models import IntegrationEvent


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


def test_failed_stage_records_marker_and_sweep_stages_event(session, monkeypatch):
    real = session.begin_nested
    calls = {"n": 0}

    def nested():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated stage failure")
        return real()
    monkeypatch.setattr(session, "begin_nested", nested)
    assert emitter.emit_for_audit(session, "org-a", "u1", "purchase_order.issued", "po-1", {}, None) is False
    monkeypatch.undo()
    session.commit()
    assert session.scalars(select(IntegrationEvent)).all() == []
    assert len(retry.outstanding(session)) == 1
    assert retry.process_due(session)["staged"] == 1
    events = session.scalars(select(IntegrationEvent)).all()
    assert len(events) == 1 and events[0].type == "asaa.payables.purchase-order-issued" and events[0].organization_id == "org-a"
    assert retry.outstanding(session) == [] and retry.process_due(session)["processed"] == 0


def test_backoff_grows_and_is_capped():
    assert [retry.backoff_seconds(n) for n in (1, 2, 3)] == [60, 120, 240] and retry.backoff_seconds(50) == 3600


def test_unknown_action_marker_is_dropped(session):
    session.add(AuditEvent(organization_id="o", actor_id="x", action=emitter.RETRY_PENDING, entity_type="integration_event", entity_id="e1",
                           outcome="pending", details={"source_action": "nope.nope", "event_data": {}}))
    session.commit()
    assert retry.process_due(session, now=datetime.now(timezone.utc) + timedelta(minutes=5))["dropped"] == 1
