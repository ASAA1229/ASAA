from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from asaa_registers.catalog import TYPES, DataError, describe, validate_data
from asaa_registers.models import GovernedRecord, utcnow

router = APIRouter(prefix="/api/v1/registers", tags=["Governed Registers"])
Db = Annotated[Session, Depends(get_db)]
CODE = r"^[A-Za-z0-9][A-Za-z0-9._-]{1,59}$"


def needs(action: str):
    """Per-register permission register:<type>:<read|write|review>. Checked before the type is resolved so unknown types give 403."""
    def dependency(rtype: str, principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if f"register:{rtype}:{action}" not in principal.permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
        if rtype not in TYPES:
            raise HTTPException(status_code=404, detail="Unknown register type")
        return principal
    return dependency


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordCreate(Strict):
    code: str = Field(pattern=CODE)
    title: str = Field(min_length=2, max_length=240)
    summary: str | None = Field(default=None, max_length=4000)
    owner_subject: str | None = Field(default=None, max_length=128)
    effective_from: date | None = None
    effective_to: date | None = None
    review_due: date | None = None
    data: dict = Field(default_factory=dict)


class RecordUpdate(Strict):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=2, max_length=240)
    summary: str | None = Field(default=None, max_length=4000)
    owner_subject: str | None = Field(default=None, max_length=128)
    effective_from: date | None = None
    effective_to: date | None = None
    review_due: date | None = None
    data: dict | None = None


class Transition(Strict):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class Review(Strict):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern="^(Approve|Reject)$")
    reason: str = Field(min_length=3, max_length=1000)


def dump(r: GovernedRecord) -> dict:
    return {"id": r.id, "register_type": r.register_type, "code": r.code, "revision": r.revision, "title": r.title, "summary": r.summary,
            "owner_subject": r.owner_subject, "status": r.status, "effective_from": r.effective_from, "effective_to": r.effective_to,
            "review_due": r.review_due, "data": r.data, "version": r.version, "created_at": r.created_at, "created_by": r.created_by,
            "updated_at": r.updated_at, "submitted_by": r.submitted_by, "reviewed_by": r.reviewed_by, "reviewed_at": r.reviewed_at,
            "review_reason": r.review_reason}


def audit(db, principal, action, record, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action, entity_type=f"register:{record.register_type}",
                      entity_id=record.id, details={"code": record.code, "revision": record.revision, **details}, correlation_id=correlation_id))


def load(db, principal, rtype, record_id) -> GovernedRecord:
    row = db.scalar(select(GovernedRecord).where(GovernedRecord.id == record_id, GovernedRecord.organization_id == principal.organization_id,
                                                 GovernedRecord.register_type == rtype))
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return row


def check_version(row, expected):
    if row.version != expected:
        raise HTTPException(status_code=409, detail={"code": "stale_record_version", "current_version": row.version})


def check_dates(effective_from, effective_to):
    if effective_from and effective_to and effective_to < effective_from:
        raise HTTPException(status_code=422, detail={"code": "effective_to_before_effective_from"})


@router.get("/types")
def register_types(principal: Annotated[Principal, Depends(get_principal)]):
    """Catalogue of register types the caller may read (field specs drive the portal forms)."""
    return [t for t in describe() if f"register:{t['key']}:read" in principal.permissions]


@router.get("/{rtype}/summary")
def summary(rtype: str, db: Db, principal: Annotated[Principal, Depends(needs("read"))]):
    base = (GovernedRecord.organization_id == principal.organization_id, GovernedRecord.register_type == rtype)
    counts = dict(db.execute(select(GovernedRecord.status, func.count()).where(*base).group_by(GovernedRecord.status)).all())
    overdue = db.scalar(select(func.count()).where(*base, GovernedRecord.review_due < date.today(), GovernedRecord.status.in_(["Approved", "In Review"]))) or 0
    return {"register_type": rtype, "by_status": {s: counts.get(s, 0) for s in ("Draft", "In Review", "Approved", "Retired")}, "review_overdue": overdue}


@router.get("/{rtype}/renewals")
def renewals(rtype: str, db: Db, principal: Annotated[Principal, Depends(needs("read"))], within_days: int = Query(default=90, ge=1, le=730)):
    """Approved records of a type with a renewal_date within the window (overdue ones first). Only the contract register has renewal dates."""
    if rtype != "contract":
        raise HTTPException(status_code=404, detail="This register has no renewal dates")
    horizon = date.today().toordinal() + within_days
    rows = db.scalars(select(GovernedRecord).where(GovernedRecord.organization_id == principal.organization_id, GovernedRecord.register_type == rtype,
                                                   GovernedRecord.status == "Approved")).all()
    due = []
    for r in rows:
        raw = (r.data or {}).get("renewal_date")
        if raw and date.fromisoformat(raw).toordinal() <= horizon:
            due.append({**dump(r), "renewal_date": raw, "days_until_renewal": date.fromisoformat(raw).toordinal() - date.today().toordinal()})
    return sorted(due, key=lambda r: r["renewal_date"])


@router.get("/{rtype}")
def list_records(rtype: str, db: Db, principal: Annotated[Principal, Depends(needs("read"))],
                 status: str | None = Query(default=None, pattern="^(Draft|In Review|Approved|Retired)$"), q: str | None = Query(default=None, max_length=100),
                 limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    stmt = select(GovernedRecord).where(GovernedRecord.organization_id == principal.organization_id, GovernedRecord.register_type == rtype)
    if status:
        stmt = stmt.where(GovernedRecord.status == status)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(GovernedRecord.title).like(like), func.lower(GovernedRecord.code).like(like)))
    rows = db.scalars(stmt.order_by(GovernedRecord.code, GovernedRecord.revision.desc()).offset(offset).limit(limit)).all()
    return [dump(r) for r in rows]


@router.post("/{rtype}", status_code=201)
def create_record(rtype: str, payload: RecordCreate, db: Db, principal: Annotated[Principal, Depends(needs("write"))],
                  x_correlation_id: Annotated[str | None, Header()] = None):
    try:
        data = validate_data(rtype, payload.data)
    except DataError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_register_data", "message": str(exc)}) from None
    check_dates(payload.effective_from, payload.effective_to)
    row = GovernedRecord(organization_id=principal.organization_id, register_type=rtype, code=payload.code, title=payload.title,
                         summary=payload.summary, owner_subject=payload.owner_subject or principal.subject, effective_from=payload.effective_from,
                         effective_to=payload.effective_to, review_due=payload.review_due, data=data, created_by=principal.subject, updated_by=principal.subject)
    db.add(row)
    try:
        db.flush()
        audit(db, principal, "register_record.created", row, {}, x_correlation_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "register_code_exists"}) from None
    return dump(row)


@router.get("/{rtype}/{record_id}")
def get_record(rtype: str, record_id: str, db: Db, principal: Annotated[Principal, Depends(needs("read"))]):
    return dump(load(db, principal, rtype, record_id))


@router.patch("/{rtype}/{record_id}")
def update_record(rtype: str, record_id: str, payload: RecordUpdate, db: Db, principal: Annotated[Principal, Depends(needs("write"))],
                  x_correlation_id: Annotated[str | None, Header()] = None):
    row = load(db, principal, rtype, record_id)
    check_version(row, payload.expected_version)
    if row.status != "Draft":
        raise HTTPException(status_code=409, detail={"code": "only_drafts_can_be_edited", "status": row.status})
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if "data" in changes:
        try:
            changes["data"] = validate_data(rtype, changes["data"] or {})
        except DataError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_register_data", "message": str(exc)}) from None
    check_dates(changes.get("effective_from", row.effective_from), changes.get("effective_to", row.effective_to))
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_by = principal.subject
    db.flush()
    audit(db, principal, "register_record.updated", row, {"changed_fields": sorted(changes)}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return dump(row)


@router.post("/{rtype}/{record_id}/submit")
def submit(rtype: str, record_id: str, payload: Transition, db: Db, principal: Annotated[Principal, Depends(needs("write"))],
           x_correlation_id: Annotated[str | None, Header()] = None):
    row = load(db, principal, rtype, record_id)
    check_version(row, payload.expected_version)
    if row.status != "Draft":
        raise HTTPException(status_code=409, detail={"code": "only_drafts_can_be_submitted", "status": row.status})
    row.status, row.submitted_by, row.updated_by = "In Review", principal.subject, principal.subject
    db.flush()
    audit(db, principal, "register_record.submitted", row, {}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return dump(row)


@router.post("/{rtype}/{record_id}/review")
def review(rtype: str, record_id: str, payload: Review, db: Db, principal: Annotated[Principal, Depends(needs("review"))],
           x_correlation_id: Annotated[str | None, Header()] = None):
    row = load(db, principal, rtype, record_id)
    check_version(row, payload.expected_version)
    if row.status != "In Review":
        raise HTTPException(status_code=409, detail={"code": "record_not_in_review", "status": row.status})
    if principal.subject in {row.created_by, row.submitted_by, row.updated_by}:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_review_own_record"})
    row.reviewed_by, row.reviewed_at, row.review_reason, row.updated_by = principal.subject, utcnow(), payload.reason, principal.subject
    if payload.decision == "Reject":
        row.status = "Draft"
    else:
        row.status = "Approved"
        row.effective_from = row.effective_from or date.today()
        for older in db.scalars(select(GovernedRecord).where(
                GovernedRecord.organization_id == principal.organization_id, GovernedRecord.register_type == rtype, GovernedRecord.code == row.code,
                GovernedRecord.status == "Approved", GovernedRecord.id != row.id)).all():
            older.status, older.effective_to, older.review_reason = "Retired", older.effective_to or date.today(), f"Superseded by revision {row.revision}"
            audit(db, principal, "register_record.superseded", older, {"superseded_by_revision": row.revision}, x_correlation_id)
    db.flush()
    audit(db, principal, "register_record.reviewed", row, {"decision": payload.decision, "reason": payload.reason}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return dump(row)


@router.post("/{rtype}/{record_id}/retire")
def retire(rtype: str, record_id: str, payload: Transition, db: Db, principal: Annotated[Principal, Depends(needs("review"))],
           x_correlation_id: Annotated[str | None, Header()] = None):
    row = load(db, principal, rtype, record_id)
    check_version(row, payload.expected_version)
    if row.status != "Approved":
        raise HTTPException(status_code=409, detail={"code": "only_approved_records_can_be_retired", "status": row.status})
    if not payload.reason or len(payload.reason.strip()) < 3:
        raise HTTPException(status_code=422, detail={"code": "reason_required"})
    row.status, row.effective_to, row.review_reason, row.updated_by = "Retired", row.effective_to or date.today(), payload.reason.strip(), principal.subject
    db.flush()
    audit(db, principal, "register_record.retired", row, {"reason": row.review_reason}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return dump(row)


@router.post("/{rtype}/{record_id}/revise", status_code=201)
def revise(rtype: str, record_id: str, payload: Transition, db: Db, principal: Annotated[Principal, Depends(needs("write"))],
           x_correlation_id: Annotated[str | None, Header()] = None):
    """Start a new Draft revision of an Approved record; the approved revision stays in force until the new one is approved."""
    row = load(db, principal, rtype, record_id)
    check_version(row, payload.expected_version)
    if row.status != "Approved":
        raise HTTPException(status_code=409, detail={"code": "only_approved_records_can_be_revised", "status": row.status})
    latest = db.scalar(select(func.max(GovernedRecord.revision)).where(
        GovernedRecord.organization_id == principal.organization_id, GovernedRecord.register_type == rtype, GovernedRecord.code == row.code)) or row.revision
    open_draft = db.scalar(select(GovernedRecord.id).where(
        GovernedRecord.organization_id == principal.organization_id, GovernedRecord.register_type == rtype, GovernedRecord.code == row.code,
        GovernedRecord.status.in_(["Draft", "In Review"])))
    if open_draft:
        raise HTTPException(status_code=409, detail={"code": "open_revision_exists", "record_id": open_draft})
    new = GovernedRecord(organization_id=row.organization_id, register_type=rtype, code=row.code, revision=latest + 1, title=row.title, summary=row.summary,
                         owner_subject=row.owner_subject, review_due=row.review_due, data=dict(row.data), created_by=principal.subject, updated_by=principal.subject)
    db.add(new)
    db.flush()
    audit(db, principal, "register_record.revised", new, {"from_revision": row.revision}, x_correlation_id)
    db.commit()
    db.refresh(new)
    return dump(new)
