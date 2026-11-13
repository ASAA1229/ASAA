import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PurchaseRequest(Base):
    __tablename__ = "ap_purchase_requests"
    __table_args__ = (
        Index("ix_ap_purchase_request_org_status", "organization_id", "status"),
        Index("ix_ap_purchase_request_org_requester", "organization_id", "requested_by"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    needed_by: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_center: Mapped[str | None] = mapped_column(String(120))
    project_reference: Mapped[str | None] = mapped_column(String(160))
    estimated_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Draft")
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    lines: Mapped[list["PurchaseRequestLine"]] = relationship(
        back_populates="purchase_request", cascade="all, delete-orphan", order_by="PurchaseRequestLine.id"
    )


class PurchaseRequestLine(Base):
    __tablename__ = "ap_purchase_request_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    purchase_request_id: Mapped[str] = mapped_column(
        ForeignKey("ap_purchase_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    estimated_unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    estimated_line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    purchase_request: Mapped[PurchaseRequest] = relationship(back_populates="lines")
