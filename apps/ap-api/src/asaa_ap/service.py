import json
import re
import uuid
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm import Session
from fastapi import HTTPException

from asaa_ap.config import get_settings
from asaa_ap.models import AuditEvent, Supplier
from asaa_ap.schemas import SupplierCreate, SupplierUpdate, StatusChange
from asaa_ap.security importdef allowed_status_transitions() -> dict[str, set[str]]:
    expected = {"Draft", "Pending Verification", "Active", "On Hold", "Suspended", "Archived"}
    try:
        raw = json.loads(get_settings().supplier_status_transitions_json)
    except (TypeError, ValueError):
        raise HTTPException(status_code=503, detail="Supplier status transition configuration is invalid") from None
    if not isinstance(raw, dict) or set(raw) != expected:
        raise HTTPException(status_code=503, detail="Supplier status transition configuration is incomplete")
    if any(not isinstance(targets, list) or any(not isinstance(target, str) or target not in expected for target in targets) for targets in raw.values()):
        raise HTTPException(status_code=503, detail="Supplier status transition configuration is invalid")
    return {state: set(targets) for state, targets in raw.items()}d": set(),
}


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def normalize_email(value: str | None) -> str | None:
    return value.casefold().strip() if value else None


def record_audit(db: Session, principal: Principal, action: str, entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(
        organization_id=principal.organization_id, actor_id=principal.subject, action=action,
        entity_type="supplier", entity_id=entity_id, details=details, correlation_id=correlation_id,
    ))


def find_duplicates(db: Session, organization_id: str, legal_name: str, email: str | None, registration_reference: str | None):
    normalized_name = normalize_name(legal_name)
    normalized_email = normalize_email(email)
    stmt = select(Supplier).where(Supplier.organization_id == organization_id)
    conditions = [Supplier.normalized_legal_name == normalized_name]
    if normalized_email:
        conditions.append(Supplier.normalized_email == normalized_email)
    if registration_reference:
        conditions.append(Supplier.registration_reference == registration_reference.strip())
    rows = db.scalars(stmt.where(or_(*conditions))).all()
    matches = []
    for row in rows:
        matched_on = []
        if row.normalized_legal_name == normalized_name:
            matched_on.append("legal_name")
        if normalized_email and row.normalized_email == normalized_email:
            matched_on.append("email")
        if registration_reference and row.registration_reference == registration_reference.strip():
            matched_on.append("registration_reference")
        matches.append({"id": row.id, "legal_name": row.legal_name, "supplier_code": row.supplier_code, "status": row.status, "matched_on": matched_on})
    return matches


def create_supplier(db: Session, payload: SupplierCreate, principal: Principal, correlation_id: str | None):
    duplicates = find_duplicates(db, principal.organization_id, payload.legal_name, str(payload.email) if payload.email else None, payload.registration_reference)
    if duplicates:
        raise HTTPException(status_code=409, detail={"code": "possible_duplicate_supplier", "matches": duplicates})
    row = Supplier(
        organization_id=principal.organization_id, supplier_code=payload.supplier_code,
        legal_name=payload.legal_name, normalized_legal_name=normalize_name(payload.legal_name),
        trading_name=payload.trading_name, email=str(payload.email) if payload.email else None,
        normalized_email=normalize_email(str(payload.email) if payload.email else None),
        phone=payload.phone, website=str(payload.website) if payload.website else None,
        category=payload.category, registration_reference=payload.registration_reference,
        addresses=[a.model_dump() for a in payload.addresses], notes=payload.notes,
        status="Draft", created_by=principal.subject, updated_by=principal.subject,
    )
    db.add(row)
    try:
        db.flush()
        record_audit(db, principal, "supplier.created", row.id, {"status": "Draft"}, correlation_id)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "supplier_conflict", "message": "Supplier code or normalized legal name already exists"}) from None


def update_supplier(db: Session, supplier_id: str, payload: SupplierUpdate, principal: Principal, correlation_id: str | None):
    row = db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    if row.status in {"Archived", "Suspended"}:
        raise HTTPException(status_code=409, detail="Supplier must be reactivated before editing")
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    identity_changed = any(key in changes for key in ("legal_name", "registration_reference"))
    if "legal_name" in changes and changes["legal_name"]:
        duplicates = find_duplicates(db, principal.organization_id, changes["legal_name"], None, None)
        if any(d["id"] != row.id for d in duplicates):
            raise HTTPException(status_code=409, detail={"code": "possible_duplicate_supplier", "matches": duplicates})
        changes["normalized_legal_name"] = normalize_name(changes["legal_name"])
    if "email" in changes:
        changes["email"] = str(changes["email"]) if changes["email"] else None
        changes["normalized_email"] = normalize_email(changes["email"])
    if "website" in changes:
        changes["website"] = str(changes["website"]) if changes["website"] else None
    if "addresses" in changes and changes["addresses"] is not None:
        changes["addresses"] = [a.model_dump() if hasattr(a, "model_dump") else a for a in changes["addresses"]]
    for key, value in changes.items():
        setattr(row, key, value)
    if identity_changed and row.status == "Active":
        row.status = "Pending Verification"
    row.updated_by = principal.subject
    try:
        db.flush()
    except StaleDataError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "version_conflict"}) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "supplier_conflict", "message": "Supplier code or normalized legal name already exists"}) from None
    record_audit(db, principal, "supplier.updated", row.id, {"changed_fields": sorted(changes), "version": row.version, "reverification_required": bool(identity_changed and row.status == "Pending Verification")}, correlation_id)
    db.commit()
    db.refresh(row)
    return row


def change_supplier_status(db: Session, supplier_id: str, payload: StatusChange, principal: Principal, correlation_id: str | None):
    row = db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == principal.organization_id))
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    if payload.status not in allowed_status_transitions()[row.status]:
        raise HTTPException(status_code=409, detail={"code": "invalid_status_transition", "from": row.status, "to": payload.status})
    if payload.status == "Active" and "supplier:verify" not in principal.permissions:
        raise HTTPException(status_code=403, detail="Supplier verification permission required")
    old_status = row.status
    row.status = payload.status
    row.updated_by = principal.subject
    try:
        db.flush()
    except StaleDataError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "version_conflict"}) from None
    record_audit(db, principal, "supplier.status_changed", row.id, {"from": old_status, "to": row.status, "reason": payload.reason, "version": row.version}, correlation_id)
    db.commit()
    db.refresh(row)
    return row
