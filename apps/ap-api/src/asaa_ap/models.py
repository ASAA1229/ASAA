import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Supplier(Base):
    __tablename__ = "ap_suppliers"
    __table_args__ = (
        UniqueConstraint("organization_id", "supplier_code", name="uq_ap_supplier_org_code"),
        UniqueConstraint("organization_id", "normalized_legal_name", name="uq_ap_supplier_org_normalized_name"),
        Index("ix_ap_supplier_org_name", "organization_id", "normalized_legal_name"),
        Index("ix_ap_supplier_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    supplier_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(240))
    email: Mapped[str | None] = mapped_column(String(320))
    normalized_email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))
    website: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(120))
    registration_reference: Mapped[str | None] = mapped_column(String(160))
    addresses: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_created", "organization_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
