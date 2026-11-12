from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_governance.models import MasterDataDomain, MasterDataRecordReference
from asaa_governance.schemas import (
    MasterDataDomainCreate, MasterDataDomainUpdate, MasterDataRecordCreate,
    MasterDataSupersede,
)

Db = Annotated[Session, Depends(get_db)]
router = APIRouter(prefix="/api/v1/master-data", tags=["Master Data Governance"])


def audit(db: Session, principal: Principal, action: str, entity_type: str,
          entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(
        organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id,
    ))


def view(row):
    return {
        key: value for key, value in row.__dict__.items()
        if not key.startswith("_") and key != "match_key_fingerprint"
    }


def domain_or_404(db: Session, domain_id: str, org_id: str):
    row = db.scalar(select(MasterDataDomain).where(
        MasterDataDomain.id == domain_id,
        MasterDataDomain.organization_id == org_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Master-data domain not found")
    return row


def record_or_404(db: Session, record_id: str, org_id: str):
    row = db.scalar(select(MasterDataRecordReference).where(
        MasterDataRecordReference.id == record_id,
        MasterDataRecordReference.organization_id == org_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Master-data record reference not found")
    return row


@router.post("/domains", status_code=201)
def create_domain(
    payload: MasterDataDomainCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("masterdata:domain:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    duplicate = db.scalar(select(MasterDataDomain.id).where(
        MasterDataDomain.organization_id == principal.organization_id,
        MasterDataDomain.domain_code == payload.domain_code,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail={"code": "master_data_domain_exists"})
    row = MasterDataDomain(
        organization_id=principal.organization_id, **payload.model_dump(),
        created_by=principal.subject, updated_by=principal.subject,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "master_data_domain_exists"}) from None
    audit(db, principal, "master_data_domain.created", "master_data_domain", row.id,
          {"domain_code": row.domain_code, "owner_subject": row.owner_subject,
           "steward_subject": row.steward_subject}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@router.get("/domains")
def list_domains(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("masterdata:domain:read"))],
    status: str | None = Query(default=None, pattern="^(Active|Inactive)$"),
):
    stmt = select(MasterDataDomain).where(
        MasterDataDomain.organization_id == principal.organization_id
    )
    if status:
        stmt = stmt.where(MasterDataDomain.status == status)
    rows = db.scalars(stmt.order_by(MasterDataDomain.domain_code)).all()
    return [view(row) for row in rows]


@router.patch("/domains/{domain_id}")
def update_domain(
    domain_id: str,
    payload: MasterDataDomainUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("masterdata:domain:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    row = domain_or_404(db, domain_id, principal.organization_id)
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "stale_master_data_domain_version"})
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "no_domain_changes"})
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_by = principal.subject
    db.flush()
    audit(db, principal, "master_data_domain.updated", "master_data_domain", row.id,
          {"changed_fields": sorted(changes), "version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@router.post("/domains/{domain_id}/records", status_code=201)
def register_record(
    domain_id: str,
    payload: MasterDataRecordCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("masterdata:record:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    domain = domain_or_404(db, domain_id, principal.organization_id)
    if domain.status != "Active":
        raise HTTPException(status_code=409, detail={"code": "master_data_domain_inactive"})
    existing = db.scalar(select(MasterDataRecordReference.id).where(
        MasterDataRecordReference.organization_id == principal.organization_id,
        MasterDataRecordReference.domain_id == domain.id,
        MasterDataRecordReference.record_type == payload.record_type,
        MasterDataRecordReference.record_id == payload.record_id,
    ))
    if existing:
        raise HTTPException(status_code=409, detail={"code": "master_data_record_reference_exists"})
    source_existing = db.scalar(select(MasterDataRecordReference.id).where(
        MasterDataRecordReference.organization_id == principal.organization_id,
        MasterDataRecordReference.domain_id == domain.id,
        MasterDataRecordReference.source_system == payload.source_system,
        MasterDataRecordReference.source_record_id == payload.source_record_id,
    ))
    if source_existing:
        raise HTTPException(status_code=409, detail={"code": "master_data_source_reference_exists"})
    duplicates = []
    if payload.match_key_fingerprint:
        duplicates = db.scalars(select(MasterDataRecordReference).where(
            MasterDataRecordReference.organization_id == principal.organization_id,
            MasterDataRecordReference.domain_id == domain.id,
            MasterDataRecordReference.match_key_fingerprint == payload.match_key_fingerprint,
            MasterDataRecordReference.status.in_({"Active", "Duplicate Review"}),
        )).all()
    row = MasterDataRecordReference(
        organization_id=principal.organization_id, domain_id=domain.id,
        **payload.model_dump(),
        status="Duplicate Review" if duplicates else "Active",
        created_by=principal.subject,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "master_data_record_conflict"}) from None
    audit(db, principal, "master_data_record.registered", "master_data_record_reference", row.id,
          {"domain_code": domain.domain_code, "record_type": row.record_type,
           "status": row.status, "duplicate_candidate_count": len(duplicates)}, x_correlation_id)
    db.commit()
    db.refresh(row)
    result = view(row)
    result["duplicate_candidates"] = [view(item) for item in duplicates]
    return result


@router.get("/domains/{domain_id}/records")
def list_records(
    domain_id: str,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("masterdata:record:read"))],
    status: str | None = Query(default=None, pattern="^(Active|Duplicate Review|Superseded|Archived)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    domain = domain_or_404(db, domain_id, principal.organization_id)
    stmt = select(MasterDataRecordReference).where(
        MasterDataRecordReference.organization_id == principal.organization_id,
        MasterDataRecordReference.domain_id == domain.id,
    )
    if status:
        stmt = stmt.where(MasterDataRecordReference.status == status)
    rows = db.scalars(stmt.order_by(MasterDataRecordReference.created_at.desc())
                      .offset(offset).limit(limit)).all()
    return [view(row) for row in rows]


@router.post("/records/{record_id}/supersede")
def supersede_record(
    record_id: str,
    payload: MasterDataSupersede,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("masterdata:record:supersede"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    row = record_or_404(db, record_id, principal.organization_id)
    if row.status not in {"Active", "Duplicate Review"}:
        raise HTTPException(status_code=409, detail={"code": "master_data_record_not_supersedable"})
    canonical = db.scalar(select(MasterDataRecordReference).where(
        MasterDataRecordReference.id == payload.canonical_record_id,
        MasterDataRecordReference.organization_id == principal.organization_id,
        MasterDataRecordReference.domain_id == row.domain_id,
        MasterDataRecordReference.status == "Active",
    ))
    if not canonical:
        raise HTTPException(status_code=404, detail="Active canonical record not found in this domain")
    if canonical.id == row.id:
        raise HTTPException(status_code=422, detail={"code": "record_cannot_supersede_itself"})
    dependent = db.scalar(select(MasterDataRecordReference.id).where(
        MasterDataRecordReference.canonical_record_id == row.id
    ))
    if dependent:
        raise HTTPException(status_code=409, detail={"code": "record_is_canonical_for_other_records"})
    row.status = "Superseded"
    row.canonical_record_id = canonical.id
    row.supersession_reason = payload.reason
    db.flush()
    audit(db, principal, "master_data_record.superseded", "master_data_record_reference", row.id,
          {"canonical_record_id": canonical.id, "reason": payload.reason}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)
