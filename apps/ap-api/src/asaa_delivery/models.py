import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class ServiceDefinition(Base):
    __tablename__ = "dlv_services"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_dlv_service_org_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_subject: Mapped[str | None] = mapped_column(String(128))
    service_tier: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(500))


class Engagement(Base):
    __tablename__ = "dlv_engagements"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_dlv_engagement_org_code"),
                      Index("ix_dlv_engagement_org_status", "organization_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("ar_customers.id"), nullable=False)
    service_id: Mapped[str | None] = mapped_column(ForeignKey("dlv_services.id"))
    sow_reference: Mapped[str | None] = mapped_column(String(160))
    project_reference: Mapped[str | None] = mapped_column(String(160))
    owner_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str | None] = mapped_column(String(3))
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Draft")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Milestone(Base):
    __tablename__ = "dlv_milestones"
    __table_args__ = (Index("ix_dlv_milestone_org_engagement", "organization_id", "engagement_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    engagement_id: Mapped[str] = mapped_column(ForeignKey("dlv_engagements.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    deliverable: Mapped[str | None] = mapped_column(String(1000))
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    billable_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Planned")
    delivered_by: Mapped[str | None] = mapped_column(String(128))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_evidence: Mapped[str | None] = mapped_column(String(500))
    accepted_by: Mapped[str | None] = mapped_column(String(128))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_acceptance_reference: Mapped[str | None] = mapped_column(String(300))
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("ar_invoices.id"))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class WorkOrder(Base):
    __tablename__ = "dlv_work_orders"
    __table_args__ = (Index("ix_dlv_work_order_org_status", "organization_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    engagement_id: Mapped[str | None] = mapped_column(ForeignKey("dlv_engagements.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(12), nullable=False, default="Normal")
    due_date: Mapped[date | None] = mapped_column(Date)
    assignee_employee_id: Mapped[str | None] = mapped_column(ForeignKey("hr_employees.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Open")
    completion_evidence: Mapped[str | None] = mapped_column(String(1000))
    completed_by: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str | None] = mapped_column(String(128))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
