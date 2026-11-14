import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdentitySubjectLink(Base):
    """Authoritative mapping between an employee record and the identity-provider subject."""
    __tablename__ = "identity_subject_links"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_id", name="uq_identity_link_org_employee"),
        UniqueConstraint("organization_id", "subject", name="uq_identity_link_org_subject"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("hr_employees.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class IdentitySyncJob(Base):
    """Transactional-outbox row. Level-triggered: the desired state is recomputed when the job runs."""
    __tablename__ = "identity_sync_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_identity_job_idempotency"),
        Index("ix_identity_job_due", "organization_id", "status", "next_attempt_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(24), nullable=False)  # joiner | mover | leaver
    reason: Mapped[str] = mapped_column(String(64), nullable=False, default="lifecycle")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Pending")  # Pending|Succeeded|DeadLetter
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(String(300))
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
