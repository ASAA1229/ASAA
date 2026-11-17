from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntegrationEvent(Base):
    """Ecosystem event envelope (asaa.event.v1). The envelope id is the primary key and the idempotency key."""
    __tablename__ = "integration_events"
    __table_args__ = (Index("ix_integration_events_org_occurred", "organization_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    project: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(200))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_by: Mapped[str] = mapped_column(String(128), nullable=False)
