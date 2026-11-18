from datetime import date, datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from asaa_ap.database import Base, get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission


def utcnow():
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationProfile(Base):
    __tablename__ = "organization_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(240))
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="Pre-Incorporation")
    country_code: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(String(300))
    registration_reference: Mapped[str | None] = mapped_column(String(160))
    registered_address: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)


class OrganizationUnit(Base):
    __tablename__ = "organization_units"
    __table_args__ = (
        UniqueConstraint("organization_id", "unit_code", name="uq_org_unit_org_code"),
        Index("ix_org_unit_org_parent", "organization_id", "parent_id"),
        Index("ix_org_unit_org_type_status", "organization_id", "unit_type", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("organization_units.id"))
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    owner_subject: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Proposed")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(String(1000))


class AccessReviewCampaign(Base):
    __tablename__ = "access_review_campaigns"
    __table_args__ = (Index("ix_access_review_org_status", "organization_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    snapshot_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class AccessReviewItem(Base):
    __tablename__ = "access_review_items"
    __table_args__ = (Index("ix_access_review_item_campaign_status", "campaign_id", "decision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("access_review_campaigns.id", ondelete="CASCADE"), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    role_code: Mapped[str | None] = mapped_column(String(128))
    permission_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    scope_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    justification: Mapped[str | None] = mapped_column(String(1000))
    decision: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending")
    review_reason: Mapped[str | None] = mapped_column(String(1000))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}


router = APIRouter(prefix="/api/v1/administration", tags=["Organization & Access Administration"])
Db = Session


class ProfileCreate(StrictModel):
    display_name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=240)
    lifecycle_status: str = Field(default="Pre-Incorporation", pattern="^(Pre-Incorporation|Active|Dormant)$")
    country_code: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    timezone: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=300)
    registration_reference: str | None = Field(default=None, max_length=160)
    registered_address: dict | None = None


class ProfileUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=240)
    lifecycle_status: str | None = Field(default=None, pattern="^(Pre-Incorporation|Active|Dormant)$")
    country_code: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    timezone: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=300)
    registration_reference: str | None = Field(default=None, max_length=160)
    registered_address: dict | None = None

    @model_validator(mode="after")
    def reject_null_required_updates(self):
        for field in ("display_name", "lifecycle_status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class UnitCreate(StrictModel):
    parent_id: str | None = None
    unit_type: str = Field(pattern="^(Legal Entity|Business Unit|Division|Department|Team|Location|Position)$")
    unit_code: str = Field(min_length=2, max_length=64, pattern="^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    owner_subject: str | None = Field(default=None, max_length=128)
    effective_from: date | None = None
    effective_to: date | None = None

    @model_validator(mode="after")
    def dates_valid(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self


class UnitUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    parent_id: str | None = None  # explicit null moves the unit to the top level
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    owner_subject: str | None = Field(default=None, max_length=128)
    effective_from: date | None = None
    effective_to: date | None = None

    @model_validator(mode="after")
    def reject_null_required_updates(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class UnitReview(StrictModel):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern="^(Approve|Reject)$")
    reason: str = Field(min_length=3, max_length=1000)


class ReviewItemInput(StrictModel):
    subject: str = Field(min_length=1, max_length=128)
    role_code: str | None = Field(default=None, max_length=128)
    permission_snapshot: list[str] = Field(min_length=1, max_length=200)
    scope_reference: str = Field(min_length=2, max_length=300)
    justification: str | None = Field(default=None, max_length=1000)


class CampaignCreate(StrictModel):
    title: str = Field(min_length=3, max_length=200)
    source_reference: str = Field(min_length=2, max_length=300)
    snapshot_as_of: datetime
    due_at: datetime | None = None
    items: list[ReviewItemInput] = Field(min_length=1, max_length=500)


class ReviewDecision(StrictModel):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern="^(Retain|Revoke|Modify)$")
    reason: str = Field(min_length=3, max_length=1000)


def audit(db, principal, action, entity_type, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id))


def dump(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


def get_unit(db, unit_id, org_id):
    row = db.scalar(select(OrganizationUnit).where(
        OrganizationUnit.id == unit_id, OrganizationUnit.organization_id == org_id))
    if not row:
        raise HTTPException(status_code=404, detail="Organization unit not found")
    return row


ALLOWED_CHILD_TYPES = {
    "Legal Entity": {"Business Unit", "Division", "Department", "Location"},
    "Business Unit": {"Division", "Department", "Team", "Location"},
    "Division": {"Department", "Team", "Location"},
    "Department": {"Team", "Position", "Location"},
    "Team": {"Position"},
    "Location": set(), "Position": set(),
}


def check_parent(db, org_id, unit_type, parent_id, unit_id=None):
    """Validate a proposed parent: it must exist in the organization, be a permitted parent type and must not create a cycle.
    unit_id is the unit being moved (None when creating, because a new unit cannot yet have descendants)."""
    if unit_id is not None and parent_id == unit_id:
        raise HTTPException(status_code=422, detail={"code": "organization_unit_self_parent"})
    parent = get_unit(db, parent_id, org_id)
    if unit_id is not None:
        seen, cursor = set(), parent
        while cursor is not None and cursor.id not in seen:
            if cursor.id == unit_id:
                raise HTTPException(status_code=422, detail={"code": "organization_unit_parent_cycle"})
            seen.add(cursor.id)
            cursor = db.scalar(select(OrganizationUnit).where(
                OrganizationUnit.id == cursor.parent_id, OrganizationUnit.organization_id == org_id)) if cursor.parent_id else None
    if unit_type not in ALLOWED_CHILD_TYPES.get(parent.unit_type, set()):
        raise HTTPException(status_code=422, detail={"code": "invalid_organization_parent_type"})
    return parent


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("organization:profile:read"))):
    row = db.scalar(select(OrganizationProfile).where(OrganizationProfile.organization_id == principal.organization_id))
    return dump(row) if row else None


@router.put("/profile")
def put_profile(payload: ProfileCreate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("organization:profile:write")),
    x_correlation_id: str | None = Header(default=None)):
    row = db.scalar(select(OrganizationProfile).where(OrganizationProfile.organization_id == principal.organization_id))
    if row:
        raise HTTPException(status_code=409, detail={"code": "organization_profile_exists_use_patch"})
    row = OrganizationProfile(organization_id=principal.organization_id, **payload.model_dump(), updated_by=principal.subject)
    db.add(row); db.flush()
    audit(db, principal, "organization_profile.created", "organization_profile", row.id,
          {"lifecycle_status": row.lifecycle_status}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.patch("/profile")
def patch_profile(payload: ProfileUpdate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("organization:profile:write")),
    x_correlation_id: str | None = Header(default=None)):
    row = db.scalar(select(OrganizationProfile).where(OrganizationProfile.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Organization profile not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_organization_profile_version"})
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "no_organization_profile_changes"})
    for key, value in changes.items(): setattr(row, key, value)
    row.updated_by = principal.subject; db.flush()
    audit(db, principal, "organization_profile.updated", "organization_profile", row.id,
          {"changed_fields": sorted(changes)}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.get("/units")
def list_units(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("organization:structure:read")),
    unit_type: str | None = None, status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    stmt = select(OrganizationUnit).where(OrganizationUnit.organization_id == principal.organization_id)
    if unit_type: stmt = stmt.where(OrganizationUnit.unit_type == unit_type)
    if status: stmt = stmt.where(OrganizationUnit.status == status)
    return [dump(row) for row in db.scalars(stmt.order_by(OrganizationUnit.unit_type, OrganizationUnit.name).offset(offset).limit(limit)).all()]


@router.post("/units", status_code=201)
def create_unit(payload: UnitCreate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("organization:structure:write")),
    x_correlation_id: str | None = Header(default=None)):
    if payload.parent_id:
        check_parent(db, principal.organization_id, payload.unit_type, payload.parent_id)
    duplicate = db.scalar(select(OrganizationUnit.id).where(
        OrganizationUnit.organization_id == principal.organization_id,
        OrganizationUnit.unit_code == payload.unit_code))
    if duplicate: raise HTTPException(status_code=409, detail={"code": "organization_unit_code_exists"})
    row = OrganizationUnit(organization_id=principal.organization_id, **payload.model_dump(),
        status="Proposed", created_by=principal.subject, updated_by=principal.subject)
    db.add(row); db.flush()
    audit(db, principal, "organization_unit.created", "organization_unit", row.id,
          {"unit_type": row.unit_type, "unit_code": row.unit_code, "parent_id": row.parent_id}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.patch("/units/{unit_id}")
def patch_unit(unit_id: str, payload: UnitUpdate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("organization:structure:write")),
    x_correlation_id: str | None = Header(default=None)):
    row = get_unit(db, unit_id, principal.organization_id)
    if row.version != payload.expected_version: raise HTTPException(status_code=409, detail={"code": "stale_organization_unit_version"})
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not changes: raise HTTPException(status_code=422, detail={"code": "no_organization_unit_changes"})
    if changes.get("parent_id"):
        check_parent(db, principal.organization_id, row.unit_type, changes["parent_id"], unit_id=row.id)
    reparented = "parent_id" in changes and changes["parent_id"] != row.parent_id
    for key, value in changes.items(): setattr(row, key, value)
    status_reset = reparented and row.status == "Active"
    if status_reset:  # a changed hierarchy position needs a fresh independent review (maker-checker)
        row.status = "Proposed"
        row.reviewed_by = row.reviewed_at = row.review_reason = None
    row.updated_by = principal.subject; db.flush()
    audit(db, principal, "organization_unit.updated", "organization_unit", row.id,
          {"changed_fields": sorted(changes), "status": row.status, "status_reset_for_review": status_reset}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.post("/units/{unit_id}/review")
def review_unit(unit_id: str, payload: UnitReview, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("organization:structure:approve")),
    x_correlation_id: str | None = Header(default=None)):
    row = get_unit(db, unit_id, principal.organization_id)
    if row.status != "Proposed":
        raise HTTPException(status_code=409, detail={"code": "organization_unit_not_proposed"})
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_organization_unit_version"})
    if principal.subject in {row.created_by, row.updated_by}:
        raise HTTPException(status_code=403, detail={"code": "organization_unit_self_approval_forbidden"})
    if payload.decision == "Approve" and row.parent_id:
        parent = get_unit(db, row.parent_id, principal.organization_id)
        if parent.status != "Active":
            raise HTTPException(status_code=409, detail={"code": "parent_unit_not_active"})
    row.status = "Active" if payload.decision == "Approve" else "Rejected"
    row.reviewed_by = principal.subject
    row.reviewed_at = utcnow()
    row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "organization_unit.reviewed", "organization_unit", row.id,
          {"decision": payload.decision, "status": row.status, "reason": payload.reason}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return dump(row)


@router.get("/access-reviews")
def list_campaigns(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("identity:access-review:read"))):
    rows = db.scalars(select(AccessReviewCampaign).where(
        AccessReviewCampaign.organization_id == principal.organization_id
    ).order_by(AccessReviewCampaign.created_at.desc())).all()
    result = []
    for row in rows:
        items = db.scalars(select(AccessReviewItem).where(
            AccessReviewItem.campaign_id == row.id,
            AccessReviewItem.organization_id == principal.organization_id)).all()
        result.append({**dump(row), "items": [dump(item) for item in items]})
    return result


@router.post("/access-reviews", status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("identity:access-review:create")),
    x_correlation_id: str | None = Header(default=None)):
    campaign = AccessReviewCampaign(organization_id=principal.organization_id,
        title=payload.title, source_reference=payload.source_reference,
        snapshot_as_of=payload.snapshot_as_of, due_at=payload.due_at,
        status="Open", created_by=principal.subject)
    db.add(campaign); db.flush()
    for item in payload.items:
        db.add(AccessReviewItem(organization_id=principal.organization_id, campaign_id=campaign.id,
            **item.model_dump(), decision="Pending"))
    audit(db, principal, "identity_access_review.created", "access_review_campaign", campaign.id,
          {"item_count": len(payload.items), "source_reference": payload.source_reference}, x_correlation_id)
    db.commit(); db.refresh(campaign)
    return {**dump(campaign), "items": [dump(item) for item in db.scalars(select(AccessReviewItem).where(AccessReviewItem.campaign_id == campaign.id)).all()]}


@router.post("/access-reviews/items/{item_id}/decision")
def decide_access_item(item_id: str, payload: ReviewDecision, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("identity:access-review:review")),
    x_correlation_id: str | None = Header(default=None)):
    item = db.scalar(select(AccessReviewItem).where(
        AccessReviewItem.id == item_id, AccessReviewItem.organization_id == principal.organization_id))
    if not item: raise HTTPException(status_code=404, detail="Access review item not found")
    if item.decision != "Pending": raise HTTPException(status_code=409, detail={"code": "access_review_item_already_decided"})
    if item.version != payload.expected_version: raise HTTPException(status_code=409, detail={"code": "stale_access_review_item_version"})
    campaign = db.scalar(select(AccessReviewCampaign).where(
        AccessReviewCampaign.id == item.campaign_id,
        AccessReviewCampaign.organization_id == principal.organization_id))
    if item.subject == principal.subject or campaign.created_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "self_access_review_forbidden"})
    item.decision = payload.decision; item.review_reason = payload.reason
    item.reviewed_by = principal.subject; item.reviewed_at = utcnow()
    db.flush()
    remaining = db.scalar(select(AccessReviewItem.id).where(
        AccessReviewItem.campaign_id == campaign.id,
        AccessReviewItem.organization_id == principal.organization_id,
        AccessReviewItem.decision == "Pending"))
    if not remaining:
        campaign.status = "Completed"
    audit(db, principal, "identity_access_review.decided", "access_review_item", item.id,
          {"subject": item.subject, "decision": item.decision, "reason": item.review_reason,
           "campaign_status": campaign.status}, x_correlation_id)
    db.commit(); db.refresh(item)
    return dump(item)
