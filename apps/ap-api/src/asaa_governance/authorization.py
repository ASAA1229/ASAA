from datetime import datetime, timezone
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from asaa_ap.database import Base, get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission


def utcnow():
    return datetime.now(timezone.utc)


class AuthorizationRoleTemplate(Base):
    __tablename__ = "authorization_role_templates"
    __table_args__ = (UniqueConstraint("organization_id", "role_code", name="uq_auth_role_org_code"), Index("ix_auth_role_org_status", "organization_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    scope_type: Mapped[str] = mapped_column(String(24), nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Proposed")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))


class AuthorizationAssignment(Base):
    __tablename__ = "authorization_assignments"
    __table_args__ = (Index("ix_auth_assignment_org_status", "organization_id", "status"),
                      Index("ix_auth_assignment_org_subject", "organization_id", "subject"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role_template_id: Mapped[str] = mapped_column(ForeignKey("authorization_role_templates.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Approval")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleCreate(StrictModel):
    role_code: str = Field(min_length=2, max_length=80, pattern="^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    scope_type: str = Field(pattern="^(Organization|Department|Project|Record)$")
    permissions: list[str] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_permissions(self):
        if len(set(self.permissions)) != len(self.permissions):
            raise ValueError("permissions must be unique")
        if any(not re.fullmatch(r"[a-z][a-z0-9_.:-]{1,127}", value) or "*" in value for value in self.permissions):
            raise ValueError("permission entries must be explicit permission identifiers; wildcards are forbidden")
        return self


class RoleUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    scope_type: str | None = Field(default=None, pattern="^(Organization|Department|Project|Record)$")
    permissions: list[str] | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_update(self):
        if not ({"name", "description", "scope_type", "permissions"} & self.model_fields_set):
            raise ValueError("at least one role template field must be updated")
        if self.permissions is not None:
            if len(set(self.permissions)) != len(self.permissions) or any(not re.fullmatch(r"[a-z][a-z0-9_.:-]{1,127}", value) or "*" in value for value in self.permissions):
                raise ValueError("permissions must be unique explicit permission identifiers")
        return self


class RoleReview(StrictModel):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern="^(Approve|Reject)$")
    reason: str = Field(min_length=3, max_length=1000)


class AssignmentCreate(StrictModel):
    role_template_id: str = Field(min_length=1, max_length=36)
    subject: str = Field(min_length=1, max_length=128)
    scope_reference: str = Field(min_length=2, max_length=300)
    effective_from: datetime
    effective_to: datetime | None = None
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_window(self):
        if self.effective_from.tzinfo is None or (self.effective_to and self.effective_to.tzinfo is None):
            raise ValueError("assignment effective dates must include a timezone")
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        return self


class AssignmentReview(StrictModel):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern="^(Approve|Reject)$")
    reason: str = Field(min_length=3, max_length=1000)


class AssignmentRevoke(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


router = APIRouter(prefix="/api/v1/authorization", tags=["Authorization Governance"])


def audit(db, principal, action, entity_type, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id))


def dump(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


def _queue_identity_sync(db, principal, subject, reason):
    """Outbox entry so provider entitlements follow approved/revoked assignments (no-op if subject is not linked)."""
    from asaa_identity.service import enqueue_for_subject_if_linked
    enqueue_for_subject_if_linked(db, principal.organization_id, subject, "mover", reason, principal.subject)


def get_role(db, role_id, org_id):
    row = db.scalar(select(AuthorizationRoleTemplate).where(
        AuthorizationRoleTemplate.id == role_id,
        AuthorizationRoleTemplate.organization_id == org_id))
    if not row:
        raise HTTPException(status_code=404, detail="Authorization role template not found")
    return row


def get_assignment(db, assignment_id, org_id):
    row = db.scalar(select(AuthorizationAssignment).where(
        AuthorizationAssignment.id == assignment_id,
        AuthorizationAssignment.organization_id == org_id))
    if not row:
        raise HTTPException(status_code=404, detail="Authorization assignment not found")
    return row


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("authorization:role:read"))):
    rows = db.scalars(select(AuthorizationRoleTemplate).where(
        AuthorizationRoleTemplate.organization_id == principal.organization_id
    ).order_by(AuthorizationRoleTemplate.role_code)).all()
    return [dump(row) for row in rows]


@router.post("/roles", status_code=201)
def create_role(payload: RoleCreate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("authorization:role:write")),
    x_correlation_id: str | None = Header(default=None)):
    duplicate = db.scalar(select(AuthorizationRoleTemplate.id).where(
        AuthorizationRoleTemplate.organization_id == principal.organization_id,
        AuthorizationRoleTemplate.role_code == payload.role_code))
    if duplicate:
        raise HTTPException(status_code=409, detail={"code": "authorization_role_code_exists"})
    row = AuthorizationRoleTemplate(organization_id=principal.organization_id,
        **payload.model_dump(), status="Proposed", created_by=principal.subject)
    db.add(row); db.flush()
    audit(db, principal, "authorization_role.proposed", "authorization_role_template", row.id,
          {"role_code": row.role_code, "scope_type": row.scope_type, "permissions": row.permissions}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.patch("/roles/{role_id}")
def update_role(role_id: str, payload: RoleUpdate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("authorization:role:write")),
    x_correlation_id: str | None = Header(default=None)):
    row = get_role(db, role_id, principal.organization_id)
    if row.status != "Proposed":
        raise HTTPException(status_code=409, detail={"code": "only_proposed_roles_are_editable"})
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_authorization_role_version"})
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    for key, value in changes.items():
        if value is not None:
            setattr(row, key, value)
    db.flush()
    audit(db, principal, "authorization_role.updated", "authorization_role_template", row.id,
          {"changed_fields": sorted(changes)}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.post("/roles/{role_id}/review")
def review_role(role_id: str, payload: RoleReview, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("authorization:role:approve")),
    x_correlation_id: str | None = Header(default=None)):
    row = get_role(db, role_id, principal.organization_id)
    if row.status != "Proposed":
        raise HTTPException(status_code=409, detail={"code": "authorization_role_not_proposed"})
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_authorization_role_version"})
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "authorization_role_self_approval_forbidden"})
    row.status = "Active" if payload.decision == "Approve" else "Rejected"
    row.reviewed_by = principal.subject; row.reviewed_at = utcnow(); row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "authorization_role.reviewed", "authorization_role_template", row.id,
          {"decision": payload.decision, "status": row.status, "reason": payload.reason}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.get("/assignments")
def list_assignments(db: Session = Depends(get_db), principal: Principal = Depends(require_permission("authorization:assignment:read")),
    status: str | None = Query(default=None, pattern="^(Pending Approval|Approved|Rejected|Revoked)$")):
    stmt = select(AuthorizationAssignment).where(AuthorizationAssignment.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(AuthorizationAssignment.status == status)
    rows = db.scalars(stmt.order_by(AuthorizationAssignment.created_at.desc())).all()
    return [dump(row) for row in rows]


@router.post("/assignments", status_code=201)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("authorization:assignment:create")),
    x_correlation_id: str | None = Header(default=None)):
    role = get_role(db, payload.role_template_id, principal.organization_id)
    if role.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "authorization_role_not_active"})
    if not payload.scope_reference.startswith(role.scope_type.lower() + ":"):
        raise HTTPException(status_code=422, detail={"code": "authorization_scope_type_mismatch"})
    row = AuthorizationAssignment(organization_id=principal.organization_id,
        **payload.model_dump(), status="Pending Approval", created_by=principal.subject)
    db.add(row); db.flush()
    audit(db, principal, "authorization_assignment.requested", "authorization_assignment", row.id,
          {"subject": row.subject, "role_code": role.role_code, "scope_reference": row.scope_reference}, x_correlation_id)
    db.commit(); db.refresh(row)
    return dump(row)


@router.post("/assignments/{assignment_id}/review")
def review_assignment(assignment_id: str, payload: AssignmentReview, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("authorization:assignment:approve")),
    x_correlation_id: str | None = Header(default=None)):
    row = get_assignment(db, assignment_id, principal.organization_id)
    if row.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "authorization_assignment_not_pending"})
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_authorization_assignment_version"})
    if principal.subject in {row.created_by, row.subject}:
        raise HTTPException(status_code=403, detail={"code": "authorization_assignment_self_review_forbidden"})
    row.status = "Approved" if payload.decision == "Approve" else "Rejected"
    row.reviewed_by = principal.subject; row.reviewed_at = utcnow(); row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "authorization_assignment.reviewed", "authorization_assignment", row.id,
          {"decision": payload.decision, "status": row.status, "reason": payload.reason}, x_correlation_id)
    _queue_identity_sync(db, principal, row.subject, "assignment_reviewed")
    db.commit(); db.refresh(row)
    return dump(row)


@router.post("/assignments/{assignment_id}/revoke")
def revoke_assignment(assignment_id: str, payload: AssignmentRevoke, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("authorization:assignment:revoke")),
    x_correlation_id: str | None = Header(default=None)):
    row = get_assignment(db, assignment_id, principal.organization_id)
    if row.status != "Approved":
        raise HTTPException(status_code=409, detail={"code": "authorization_assignment_not_revocable"})
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_authorization_assignment_version"})
    row.status = "Revoked"; row.reviewed_by = principal.subject; row.reviewed_at = utcnow(); row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "authorization_assignment.revoked", "authorization_assignment", row.id,
          {"subject": row.subject, "reason": payload.reason}, x_correlation_id)
    _queue_identity_sync(db, principal, row.subject, "assignment_revoked")
    db.commit(); db.refresh(row)
    return dump(row)
