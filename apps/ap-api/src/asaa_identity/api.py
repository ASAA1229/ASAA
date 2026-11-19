from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.config import get_settings
from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_identity import service
from asaa_identity.models import IdentityAdoptionRequest, IdentitySubjectLink, IdentitySyncJob
from asaa_identity.provider import IdentityProvider, PermanentProviderError, TransientProviderError, resolve_provider
from asaa_people.models import Employee

router = APIRouter(prefix="/api/v1/identity-sync", tags=["Identity Lifecycle"])
Db = Annotated[Session, Depends(get_db)]


def get_identity_provider() -> IdentityProvider:
    provider = resolve_provider(get_settings().identity_provider)
    if provider is None:
        raise HTTPException(status_code=503, detail="No identity provider adapter is configured")
    return provider


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LinkWrite(Strict):
    employee_id: str = Field(min_length=1, max_length=36)
    subject: str = Field(min_length=1, max_length=128)


class JobCreate(Strict):
    employee_id: str | None = Field(default=None, max_length=36)
    operation: str = Field(pattern="^(joiner|mover|leaver)$")
    reason: str = Field(min_length=3, max_length=64, default="manual")

    @model_validator(mode="after")
    def need_employee(self):
        if not self.employee_id:
            raise ValueError("employee_id is required")
        return self


def dump(job: IdentitySyncJob) -> dict:
    return {"id": job.id, "subject": job.subject, "operation": job.operation, "reason": job.reason, "status": job.status,
            "attempts": job.attempts, "max_attempts": job.max_attempts, "next_attempt_at": job.next_attempt_at,
            "last_error": job.last_error, "requested_at": job.requested_at, "completed_at": job.completed_at}


def _audit(db, principal, action, entity_type, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject, action=action,
                      entity_type=entity_type, entity_id=entity_id, details=details, correlation_id=correlation_id))


@router.put("/links")
def link_employee(payload: LinkWrite, db: Db, principal: Annotated[Principal, Depends(require_permission("identity:link:write"))],
                  x_correlation_id: Annotated[str | None, Header()] = None):
    employee = db.scalar(select(Employee).where(Employee.id == payload.employee_id, Employee.organization_id == principal.organization_id))
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    link = db.scalar(select(IdentitySubjectLink).where(
        IdentitySubjectLink.organization_id == principal.organization_id, IdentitySubjectLink.employee_id == employee.id))
    if link:
        link.subject = payload.subject
    else:
        link = IdentitySubjectLink(organization_id=principal.organization_id, employee_id=employee.id,
                                   subject=payload.subject, created_by=principal.subject)
        db.add(link)
    try:
        db.flush()
        _audit(db, principal, "identity_link.set", "identity_subject_link", link.id, {"employee_id": employee.id}, x_correlation_id)
        service.enqueue(db, principal.organization_id, link.subject, "joiner", "link_created", principal.subject)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "identity_subject_already_linked"}) from None
    return {"id": link.id, "employee_id": link.employee_id, "subject": link.subject}


@router.get("/links")
def list_links(db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:read"))]):
    rows = db.scalars(select(IdentitySubjectLink).where(IdentitySubjectLink.organization_id == principal.organization_id)).all()
    return [{"id": r.id, "employee_id": r.employee_id, "subject": r.subject} for r in rows]


@router.post("/jobs", status_code=201)
def create_job(payload: JobCreate, db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:enqueue"))],
               x_correlation_id: Annotated[str | None, Header()] = None):
    job = service.enqueue_for_employee(db, principal.organization_id, payload.employee_id, payload.operation, payload.reason, principal.subject)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "employee_not_linked_to_identity_subject"})
    _audit(db, principal, "identity_sync.enqueued", "identity_sync_job", job.id, {"operation": job.operation}, x_correlation_id)
    db.commit()
    return dump(job)


@router.get("/jobs")
def list_jobs(db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:read"))],
              status: str | None = Query(default=None, pattern="^(Pending|Succeeded|DeadLetter|NotFound)$"), limit: int = Query(default=100, ge=1, le=500)):
    stmt = select(IdentitySyncJob).where(IdentitySyncJob.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(IdentitySyncJob.status == status)
    return [dump(j) for j in db.scalars(stmt.order_by(IdentitySyncJob.requested_at.desc()).limit(limit)).all()]


@router.get("/status")
def sync_status(db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:read"))]):
    return service.status_summary(db, principal.organization_id)


@router.post("/process")
def process(db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:run"))],
            provider: Annotated[IdentityProvider, Depends(get_identity_provider)], limit: int = Query(default=50, ge=1, le=200)):
    return service.process_due(db, provider, principal.organization_id, limit=limit)


@router.post("/jobs/{job_id}/retry")
def retry(job_id: str, db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:run"))]):
    job = service.retry_dead_letter(db, principal.organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Dead-letter job not found")
    return dump(job)


@router.post("/reconcile")
def reconcile(db: Db, principal: Annotated[Principal, Depends(require_permission("identity:sync:reconcile"))],
              provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
              repair: bool = False):
    if repair and "identity:sync:enqueue" not in principal.permissions:
        raise HTTPException(status_code=403, detail="Permission denied")
    return service.reconcile(db, provider, principal.organization_id, repair=repair, actor=principal.subject)


# ---------------------------------------------------------------- one-time adoption of existing accounts (maker-checker)

class AdoptionCreate(Strict):
    employee_id: str = Field(min_length=1, max_length=36)
    provider_username: str = Field(min_length=1, max_length=128, pattern=r"^[^\s/\\?#%]+$")
    reason: str = Field(min_length=3, max_length=500)


class AdoptionReview(Strict):
    decision: str = Field(pattern="^(Approve|Reject)$")
    reason: str = Field(min_length=3, max_length=500)


def dump_adoption(row: IdentityAdoptionRequest) -> dict:
    return {"id": row.id, "employee_id": row.employee_id, "subject": row.subject, "provider_username": row.provider_username,
            "reason": row.reason, "status": row.status, "requested_by": row.requested_by, "requested_at": row.requested_at,
            "reviewed_by": row.reviewed_by, "reviewed_at": row.reviewed_at, "review_reason": row.review_reason, "result": row.result}


@router.post("/adoptions", status_code=201)
def request_adoption(payload: AdoptionCreate, db: Db,
                     principal: Annotated[Principal, Depends(require_permission("identity:adoption:request"))],
                     x_correlation_id: Annotated[str | None, Header()] = None):
    """Ask to adopt a pre-existing provider account for a linked employee. Nothing happens until a different person approves."""
    link = db.scalar(select(IdentitySubjectLink).where(
        IdentitySubjectLink.organization_id == principal.organization_id, IdentitySubjectLink.employee_id == payload.employee_id))
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "employee_not_linked_to_identity_subject"})
    pending = db.scalar(select(IdentityAdoptionRequest.id).where(
        IdentityAdoptionRequest.organization_id == principal.organization_id, IdentityAdoptionRequest.employee_id == payload.employee_id,
        IdentityAdoptionRequest.status == "Pending"))
    if pending:
        raise HTTPException(status_code=409, detail={"code": "adoption_already_pending"})
    row = IdentityAdoptionRequest(organization_id=principal.organization_id, employee_id=payload.employee_id, subject=link.subject,
                                  provider_username=payload.provider_username, reason=payload.reason, requested_by=principal.subject)
    db.add(row)
    db.flush()
    _audit(db, principal, "identity_adoption.requested", "identity_adoption_request", row.id,
           {"employee_id": row.employee_id, "provider_username": row.provider_username}, x_correlation_id)
    db.commit()
    return dump_adoption(row)


@router.get("/adoptions")
def list_adoptions(db: Db, principal: Annotated[Principal, Depends(require_permission("identity:adoption:read"))],
                   status: str | None = Query(default=None, pattern="^(Pending|Approved|Rejected|Failed)$"),
                   limit: int = Query(default=100, ge=1, le=500)):
    stmt = select(IdentityAdoptionRequest).where(IdentityAdoptionRequest.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(IdentityAdoptionRequest.status == status)
    return [dump_adoption(r) for r in db.scalars(stmt.order_by(IdentityAdoptionRequest.requested_at.desc()).limit(limit)).all()]


@router.post("/adoptions/{adoption_id}/review")
def review_adoption(adoption_id: str, payload: AdoptionReview, db: Db,
                    principal: Annotated[Principal, Depends(require_permission("identity:adoption:approve"))],
                    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
                    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(IdentityAdoptionRequest).where(
        IdentityAdoptionRequest.id == adoption_id, IdentityAdoptionRequest.organization_id == principal.organization_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Adoption request not found")
    if row.status != "Pending":
        raise HTTPException(status_code=409, detail={"code": "adoption_not_pending"})
    if row.requested_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "adoption_self_approval_forbidden"})
    row.reviewed_by, row.reviewed_at, row.review_reason = principal.subject, service.utcnow(), payload.reason
    if payload.decision == "Reject":
        row.status = "Rejected"
        _audit(db, principal, "identity_adoption.rejected", "identity_adoption_request", row.id, {"employee_id": row.employee_id}, x_correlation_id)
        db.commit()
        return dump_adoption(row)
    employee = db.scalar(select(Employee).where(Employee.id == row.employee_id, Employee.organization_id == principal.organization_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        provider_id = provider.adopt_account(row.subject, row.provider_username, employee.employee_code, employee.work_email)
    except TransientProviderError:
        db.rollback()
        raise HTTPException(status_code=503, detail={"code": "identity_provider_unavailable"}) from None
    except PermanentProviderError as exc:
        row.status, row.result = "Failed", str(exc)[:300]
        _audit(db, principal, "identity_adoption.failed", "identity_adoption_request", row.id, {"employee_id": row.employee_id}, x_correlation_id)
        db.commit()
        raise HTTPException(status_code=422, detail={"code": "adoption_refused", "message": row.result}) from None
    row.status, row.result = "Approved", "adopted"
    _audit(db, principal, "identity_adoption.approved", "identity_adoption_request", row.id,
           {"employee_id": row.employee_id, "provider_id": provider_id, "requested_by": row.requested_by}, x_correlation_id)
    service.enqueue(db, principal.organization_id, row.subject, "mover", "adoption", principal.subject)  # converge groups and attributes
    db.commit()
    return dump_adoption(row)
