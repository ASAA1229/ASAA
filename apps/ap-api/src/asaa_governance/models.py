import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from asaa_ap.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MasterDataDomain(Base):
    __tablename__ = "master_data_domains"
    __table_args__ = (
        UniqueConstraint("organization_id", "domain_code", name="uq_master_data_domain_org_code"),
        Index("ix_master_data_domain_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    authoritative_source: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    steward_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)


class MasterDataRecordReference(Base):
    __tablename__ = "master_data_record_references"
    __table_args__ = (
        UniqueConstraint("organization_id", "domain_id", "record_type", "record_id",
                         name="uq_master_data_record_identity"),
        UniqueConstraint("organization_id", "domain_id", "source_system", "source_record_id",
                         name="uq_master_data_source_identity"),
        Index("ix_master_data_record_match", "organization_id", "domain_id", "match_key_fingerprint", "status"),
        Index("ix_master_data_record_domain_status", "organization_id", "domain_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_id: Mapped[str] = mapped_column(ForeignKey("master_data_domains.id"), nullable=False)
    record_type: Mapped[str] = mapped_column(String(80), nullable=False)
    record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    match_key_fingerprint: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Active")
    canonical_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("master_data_record_references.id")
    )
    supersession_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
