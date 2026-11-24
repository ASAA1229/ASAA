from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from asaa_ap.database import Base, get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AuthorityDelegation(Base):
    __tablename__ = "authority_delegations"
    __table_args__ = (
        Index("ix_authority_delegation_org_status", "organization_id", "status"),
        Index("ix_authority_delegation_org_subjects", "organization_id", "delegator_subject", "delegate_subject"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    delegator_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    delegate_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_code: Mapped[str] = mapped_column(String(160), nullable=False)
    action_code: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Pending Approval")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))


class GovernanceDecision(Base):
    __tablename__ = "governance_decisions"
    __table_args__ = (
        Index("ix_governance_decision_org_status", "organization_id", "status"),
        Index("ix_governance_decision_org_maker", "organization_id", "decision_maker_subject"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    scope_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decision_maker_subject: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="Proposed")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    review_reason: Mapped[str | None] = mapped_column(String(1000))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DelegationCreate(StrictModel):
    delegator_subject: str = Field(min_length=1, max_length=128)
    delegate_subject: str = Field(min_length=1, max_length=128)
    scope_code: str = Field(min_length=2, max_length=160)
    action_code: str = Field(min_length=2, max_length=160)
    effective_from: datetime
    effective_to: datetime
    reason: str = Field(min_length=3, max_length=1000)
    evidence_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_delegation(self):
        if self.delegator_subject == self.delegate_subject:
            raise ValueError("delegator and delegate must be different subjects")
        if as_utc(self.effective_to) <= as_utc(self.effective_from):
            raise ValueError("effective_to must be later than effective_from")
        return self


class DecisionCreate(StrictModel):
    decision_type: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=240)
    scope_reference: str = Field(min_length=2, max_length=500)
    rationale: str = Field(min_length=3, max_length=4000)
    decision_maker_subject: str = Field(min_length=1, max_length=128)
    effective_at: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=500)


class ReviewAction(StrictModel):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=3, max_length=1000)


router = APIRouter(prefix="/api/v1/governance", tags=["Governance Authority"])


def audit(db: Session, principal: Principal, action: str, entity_type: str,
          entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(
        organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id,
    ))


def serialize(row):
    result = {key: value for key, value in row.__dict__.items() if not key.startswith("_")}
    if isinstance(row, AuthorityDelegation):
        now = utcnow()
        result["effective_now"] = (
            row.status == "Approved"
            and as_utc(row.effective_from) <= now < as_utc(row.effective_to)
        )
    return result


def get_delegation(db: Session, record_id: str, org_id: str):
    row = db.scalar(select(AuthorityDelegation).where(
        AuthorityDelegation.id == record_id,
        AuthorityDelegation.organization_id == org_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Delegation not found")
    return row


def get_decision(db: Session, record_id: str, org_id: str):
    row = db.scalar(select(GovernanceDecision).where(
        GovernanceDecision.id == record_id,
        GovernanceDecision.organization_id == org_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@router.post("/delegations", status_code=201)
def create_delegation(
    payload: DelegationCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:delegation:create")),
    x_correlation_id: str | None = Header(default=None),
):
    row = AuthorityDelegation(
        organization_id=principal.organization_id, **payload.model_dump(),
        status="Pending Approval", created_by=principal.subject,
    )
    db.add(row)
    db.flush()
    audit(db, principal, "authority_delegation.created", "authority_delegation", row.id,
          {"delegator_subject": row.delegator_subject, "delegate_subject": row.delegate_subject,
           "scope_code": row.scope_code, "action_code": row.action_code,
           "effective_from": as_utc(row.effective_from).isoformat(),
           "effective_to": as_utc(row.effective_to).isoformat()}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/delegations")
def list_delegations(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:delegation:read")),
    status: str | None = Query(default=None, pattern="^(Pending Approval|Approved|Rejected|Revoked|Expired)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(AuthorityDelegation).where(
        AuthorityDelegation.organization_id == principal.organization_id
    )
    if status:
        stmt = stmt.where(AuthorityDelegation.status == status)
    rows = db.scalars(stmt.order_by(AuthorityDelegation.created_at.desc())
                      .offset(offset).limit(limit)).all()
    return [serialize(row) for row in rows]


@router.post("/delegations/expire-due")
def expire_due_delegations(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:delegation:revoke")),
    x_correlation_id: str | None = Header(default=None),
):
    """Persist expiry: Approved delegations whose window has ended become Expired (audited). Read-time evaluation of
    effective_now is unchanged; this makes the lapsed state durable and visible in lists and reports."""
    now = utcnow()
    rows = db.scalars(select(AuthorityDelegation).where(
        AuthorityDelegation.organization_id == principal.organization_id,
        AuthorityDelegation.status == "Approved")).all()
    expired = [row for row in rows if as_utc(row.effective_to) <= now]
    for row in expired:
        row.status = "Expired"
        db.flush()
        audit(db, principal, "authority_delegation.expired", "authority_delegation", row.id,
              {"effective_to": as_utc(row.effective_to).isoformat(), "version": row.version}, x_correlation_id)
    db.commit()
    return {"expired": len(expired), "ids": [row.id for row in expired]}


@router.post("/delegations/{delegation_id}/approve")
def approve_delegation(
    delegation_id: str, payload: ReviewAction, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:delegation:approve")),
    x_correlation_id: str | None = Header(default=None),
):
    row = get_delegation(db, delegation_id, principal.organization_id)
    if row.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "delegation_not_pending"})
    if payload.expected_version != row.version:
        raise HTTPException(status_code=409, detail={"code": "stale_delegation_version"})
    if principal.subject in {row.created_by, row.delegator_subject, row.delegate_subject}:
        raise HTTPException(status_code=403, detail={"code": "delegation_self_approval_forbidden"})
    row.status, row.reviewed_by, row.reviewed_at = "Approved", principal.subject, utcnow()
    row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "authority_delegation.approved", "authority_delegation", row.id,
          {"version": row.version, "effective_now": as_utc(row.effective_from) <= utcnow() < as_utc(row.effective_to)},
          x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/delegations/{delegation_id}/reject")
def reject_delegation(
    delegation_id: str, payload: ReviewAction, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:delegation:reject")),
    x_correlation_id: str | None = Header(default=None),
):
    row = get_delegation(db, delegation_id, principal.organization_id)
    if row.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "delegation_not_pending"})
    if payload.expected_version != row.version:
        raise HTTPException(status_code=409, detail={"code": "stale_delegation_version"})
    if not payload.reason:
        raise HTTPException(status_code=422, detail={"code": "rejection_reason_required"})
    if principal.subject in {row.created_by, row.delegator_subject, row.delegate_subject}:
        raise HTTPException(status_code=403, detail={"code": "delegation_self_review_forbidden"})
    row.status, row.reviewed_by, row.reviewed_at = "Rejected", principal.subject, utcnow()
    row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "authority_delegation.rejected", "authority_delegation", row.id,
          {"reason": payload.reason, "version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/delegations/{delegation_id}/revoke")
def revoke_delegation(
    delegation_id: str, payload: ReviewAction, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:delegation:revoke")),
    x_correlation_id: str | None = Header(default=None),
):
    row = get_delegation(db, delegation_id, principal.organization_id)
    if row.status != "Approved":
        raise HTTPException(status_code=409, detail={"code": "delegation_not_revocable"})
    if payload.expected_version != row.version:
        raise HTTPException(status_code=409, detail={"code": "stale_delegation_version"})
    if not payload.reason:
        raise HTTPException(status_code=422, detail={"code": "revocation_reason_required"})
    row.status, row.reviewed_by, row.reviewed_at = "Revoked", principal.subject, utcnow()
    row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "authority_delegation.revoked", "authority_delegation", row.id,
          {"reason": payload.reason, "version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/decisions", status_code=201)
def create_decision(
    payload: DecisionCreate, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:decision:create")),
    x_correlation_id: str | None = Header(default=None),
):
    row = GovernanceDecision(
        organization_id=principal.organization_id, **payload.model_dump(),
        status="Proposed", created_by=principal.subject,
    )
    db.add(row)
    db.flush()
    audit(db, principal, "governance_decision.proposed", "governance_decision", row.id,
          {"decision_type": row.decision_type, "decision_maker_subject": row.decision_maker_subject,
           "scope_reference": row.scope_reference}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/decisions")
def list_decisions(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:decision:read")),
    status: str | None = Query(default=None, pattern="^(Proposed|Approved|Rejected)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(GovernanceDecision).where(
        GovernanceDecision.organization_id == principal.organization_id
    )
    if status:
        stmt = stmt.where(GovernanceDecision.status == status)
    rows = db.scalars(stmt.order_by(GovernanceDecision.created_at.desc())
                      .offset(offset).limit(limit)).all()
    return [serialize(row) for row in rows]


@router.post("/decisions/{decision_id}/approve")
def approve_decision(
    decision_id: str, payload: ReviewAction, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:decision:approve")),
    x_correlation_id: str | None = Header(default=None),
):
    row = get_decision(db, decision_id, principal.organization_id)
    if row.status != "Proposed":
        raise HTTPException(status_code=409, detail={"code": "decision_not_proposed"})
    if payload.expected_version != row.version:
        raise HTTPException(status_code=409, detail={"code": "stale_decision_version"})
    if principal.subject != row.decision_maker_subject or principal.subject == row.created_by:
        raise HTTPException(status_code=403, detail={"code": "decision_maker_only_and_no_self_approval"})
    row.status, row.reviewed_by, row.reviewed_at = "Approved", principal.subject, utcnow()
    row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "governance_decision.approved", "governance_decision", row.id,
          {"version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/decisions/{decision_id}/reject")
def reject_decision(
    decision_id: str, payload: ReviewAction, db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission("governance:decision:reject")),
    x_correlation_id: str | None = Header(default=None),
):
    row = get_decision(db, decision_id, principal.organization_id)
    if row.status != "Proposed":
        raise HTTPException(status_code=409, detail={"code": "decision_not_proposed"})
    if payload.expected_version != row.version:
        raise HTTPException(status_code=409, detail={"code": "stale_decision_version"})
    if principal.subject != row.decision_maker_subject or principal.subject == row.created_by:
        raise HTTPException(status_code=403, detail={"code": "decision_maker_only_and_no_self_review"})
    if not payload.reason:
        raise HTTPException(status_code=422, detail={"code": "rejection_reason_required"})
    row.status, row.reviewed_by, row.reviewed_at = "Rejected", principal.subject, utcnow()
    row.review_reason = payload.reason
    db.flush()
    audit(db, principal, "governance_decision.rejected", "governance_decision", row.id,
          {"reason": payload.reason, "version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)
