from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_integration.emitter import emit_for_audit
from asaa_workforce_finance.models import Timesheet, TimeEntry, ExpenseClaim, ExpensePolicyRule
from asaa_workforce_finance.schemas import (TimesheetCreate, TimesheetRead, TimesheetReview, ExpenseCreate, ExpenseRead, ExpenseReview, ExpenseReimbursement,
    ExpenseUpdate, TimesheetUpdate, PolicyRuleWrite)

router = APIRouter(prefix="/api/v1/workforce-finance", tags=["Timesheets and Expenses"])
Db = Annotated[Session, Depends(get_db)]

def audit(db, principal, action, kind, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=kind, entity_id=entity_id, details=details,
        correlation_id=correlation_id))
    emit_for_audit(db, principal.organization_id, principal.subject, action, entity_id, details, correlation_id)

def owned_timesheet(db, timesheet_id, org):
    row = db.scalar(select(Timesheet).where(Timesheet.id == timesheet_id, Timesheet.organization_id == org))
    if not row:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return row

def check_timesheet_rules(db, org, subject, start, end, entries, exclude_id=None):
    """Duplicate entries (same date, project and task) are rejected, and an employee may not hold two non-rejected timesheets with overlapping periods."""
    seen = set()
    for e in entries:
        key = (e.work_date, (e.project_reference or "").strip().lower(), (e.task_reference or "").strip().lower())
        if key in seen:
            raise HTTPException(status_code=409, detail={"code": "duplicate_time_entry", "work_date": e.work_date.isoformat()})
        seen.add(key)
    stmt = select(Timesheet.id).where(Timesheet.organization_id == org, Timesheet.employee_subject == subject, Timesheet.status != "Rejected",
                                      Timesheet.period_start <= end, Timesheet.period_end >= start)
    if exclude_id:
        stmt = stmt.where(Timesheet.id != exclude_id)
    if db.scalar(stmt.limit(1)):
        raise HTTPException(status_code=409, detail={"code": "timesheet_period_overlap"})

def owned_expense(db, claim_id, org):
    row = db.scalar(select(ExpenseClaim).where(ExpenseClaim.id == claim_id, ExpenseClaim.organization_id == org))
    if not row:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    return row

@router.post("/timesheets", response_model=TimesheetRead, status_code=201)
def create_timesheet(payload: TimesheetCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("tms:timesheet:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    check_timesheet_rules(db, principal.organization_id, principal.subject, payload.period_start, payload.period_end, payload.entries)
    row = Timesheet(organization_id=principal.organization_id, employee_subject=principal.subject,
        employee_reference=payload.employee_reference, period_start=payload.period_start,
        period_end=payload.period_end, status="Draft",
        total_hours=sum((e.hours for e in payload.entries), start=0),
        created_by=principal.subject)
    db.add(row)
    db.flush()
    for entry in payload.entries:
        db.add(TimeEntry(organization_id=principal.organization_id, timesheet_id=row.id,
            work_date=entry.work_date, project_reference=entry.project_reference,
            task_reference=entry.task_reference, description=entry.description,
            hours=entry.hours, billable=entry.billable))
    audit(db, principal, "timesheet.created", "timesheet", row.id,
        {"total_hours": str(row.total_hours), "entry_count": len(payload.entries)}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row

@router.get("/timesheets", response_model=list[TimesheetRead])
def list_timesheets(db: Db, principal: Annotated[Principal, Depends(require_permission("tms:timesheet:read"))],
    status: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(Timesheet).where(Timesheet.organization_id == principal.organization_id)
    if "tms:timesheet:read:all" not in principal.permissions:
        stmt = stmt.where(Timesheet.employee_subject == principal.subject)
    if status:
        stmt = stmt.where(Timesheet.status == status)
    return db.scalars(stmt.order_by(Timesheet.created_at.desc()).offset(offset).limit(limit)).all()

@router.post("/timesheets/{timesheet_id}/submit", response_model=TimesheetRead)
def submit_timesheet(timesheet_id: str, payload: TimesheetReview, db: Db,
    principal: Annotated[Principal, Depends(require_permission("tms:timesheet:submit"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = owned_timesheet(db, timesheet_id, principal.organization_id)
    if row.employee_subject != principal.subject or row.status not in {"Draft", "Rejected"}:
        raise HTTPException(status_code=409, detail="Only the owner can submit a Draft or Rejected timesheet")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    row.status, row.review_reason, row.reviewed_at, row.reviewed_by = "Submitted", payload.reason, None, None
    audit(db, principal, "timesheet.submitted", "timesheet", row.id, {"version": row.version}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row

@router.post("/timesheets/{timesheet_id}/review", response_model=TimesheetRead)
def review_timesheet(timesheet_id: str, payload: TimesheetReview, db: Db,
    principal: Annotated[Principal, Depends(require_permission("tms:timesheet:review"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = owned_timesheet(db, timesheet_id, principal.organization_id)
    if row.employee_subject == principal.subject:
        raise HTTPException(status_code=403, detail="Maker cannot review own timesheet")
    if row.status != "Submitted" or row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Timesheet is not reviewable or version is stale")
    if payload.decision is None:
        raise HTTPException(status_code=422, detail="decision must be approve or reject")
    row.status = "Approved" if payload.decision == "approve" else "Rejected"
    row.review_reason, row.reviewed_at, row.reviewed_by = payload.reason, datetime.now(timezone.utc), principal.subject
    audit(db, principal, "timesheet.reviewed", "timesheet", row.id, {"status": row.status}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row

@router.post("/expenses", response_model=ExpenseRead, status_code=201)
def create_expense(payload: ExpenseCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("expense:claim:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = ExpenseClaim(organization_id=principal.organization_id, employee_subject=principal.subject,
        expense_date=payload.expense_date, category_code=payload.category_code,
        merchant=payload.merchant, description=payload.description, amount=payload.amount,
        currency=payload.currency, receipt_reference=payload.receipt_reference,
        project_reference=payload.project_reference, status="Draft", created_by=principal.subject)
    db.add(row)
    db.flush()
    audit(db, principal, "expense.created", "expense_claim", row.id,
        {"amount": str(row.amount), "currency": row.currency}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row

@router.get("/expenses", response_model=list[ExpenseRead])
def list_expenses(db: Db, principal: Annotated[Principal, Depends(require_permission("expense:claim:read"))],
    status: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    stmt = select(ExpenseClaim).where(ExpenseClaim.organization_id == principal.organization_id)
    if "expense:claim:read:all" not in principal.permissions:
        stmt = stmt.where(ExpenseClaim.employee_subject == principal.subject)
    if status:
        stmt = stmt.where(ExpenseClaim.status == status)
    return db.scalars(stmt.order_by(ExpenseClaim.created_at.desc()).offset(offset).limit(limit)).all()

@router.post("/expenses/{claim_id}/submit", response_model=ExpenseRead)
def submit_expense(claim_id: str, payload: ExpenseReview, db: Db,
    principal: Annotated[Principal, Depends(require_permission("expense:claim:submit"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = owned_expense(db, claim_id, principal.organization_id)
    if row.employee_subject != principal.subject or row.status not in {"Draft", "Rejected"}:
        raise HTTPException(status_code=409, detail="Only the owner can submit a Draft or Rejected claim")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    flags = evaluate_policy(db, row)
    blocking = [f for f in flags if f["action"] == "block"]
    if blocking:
        raise HTTPException(status_code=409, detail={"code": "expense_policy_violation", "violations": [f["rule"] for f in blocking]})
    row.policy_flags = flags or None
    row.status, row.review_reason = "Submitted", payload.reason
    audit(db, principal, "expense.submitted", "expense_claim", row.id, {"policy_flags": [f["rule"] for f in flags]}, x_correlation_id)
    for flag in flags:
        audit(db, principal, "expense_claim.policy_flagged", "expense_claim", row.id, {"rule": flag["rule"]}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row

@router.post("/expenses/{claim_id}/review", response_model=ExpenseRead)
def review_expense(claim_id: str, payload: ExpenseReview, db: Db,
    principal: Annotated[Principal, Depends(require_permission("expense:claim:review"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = owned_expense(db, claim_id, principal.organization_id)
    if row.employee_subject == principal.subject:
        raise HTTPException(status_code=403, detail="Maker cannot review own expense claim")
    if row.status != "Submitted" or row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Expense claim is not reviewable or version is stale")
    if payload.decision is None:
        raise HTTPException(status_code=422, detail="decision must be approve or reject")
    row.status = "Approved" if payload.decision == "approve" else "Rejected"
    row.review_reason, row.reviewed_at, row.reviewed_by = payload.reason, datetime.now(timezone.utc), principal.subject
    audit(db, principal, "expense.reviewed", "expense_claim", row.id, {"status": row.status}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row

@router.post("/expenses/{claim_id}/reimburse", response_model=ExpenseRead)
def reimburse_expense(claim_id: str, payload: ExpenseReimbursement, db: Db,
    principal: Annotated[Principal, Depends(require_permission("expense:claim:reimburse"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = owned_expense(db, claim_id, principal.organization_id)
    if row.status != "Approved" or row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Only an approved claim with the current version can be reimbursed")
    if row.employee_subject == principal.subject:
        raise HTTPException(status_code=403, detail="Claim owner cannot record own reimbursement")
    row.status, row.reimbursed_at, row.reimbursed_by = "Reimbursement Recorded", datetime.now(timezone.utc), principal.subject
    row.reimbursement_reference = payload.reimbursement_reference
    audit(db, principal, "expense.reimbursed", "expense_claim", row.id,
        {"reimbursement_reference": payload.reimbursement_reference}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


def evaluate_policy(db: Session, claim: ExpenseClaim) -> list[dict]:
    """Rule violations for a claim. Only Approved owner-set rules apply; the duplicate check is neutral (same owner, date, amount, currency, merchant)."""
    flags: list[dict] = []
    rule = db.scalar(select(ExpensePolicyRule).where(ExpensePolicyRule.organization_id == claim.organization_id, ExpensePolicyRule.category_code == claim.category_code,
                                                     ExpensePolicyRule.status == "Approved", ExpensePolicyRule.currency == claim.currency))
    if rule:
        if rule.max_amount is not None and claim.amount > rule.max_amount:
            flags.append({"rule": "amount_exceeds_category_limit", "action": rule.on_violation})
        if rule.receipt_required_above is not None and claim.amount > rule.receipt_required_above and not claim.receipt_reference:
            flags.append({"rule": "receipt_required", "action": rule.on_violation})
    dup = db.scalar(select(ExpenseClaim.id).where(ExpenseClaim.organization_id == claim.organization_id, ExpenseClaim.employee_subject == claim.employee_subject,
                                                  ExpenseClaim.id != claim.id, ExpenseClaim.expense_date == claim.expense_date, ExpenseClaim.amount == claim.amount,
                                                  ExpenseClaim.currency == claim.currency, ExpenseClaim.merchant == claim.merchant,
                                                  ExpenseClaim.status.in_(["Submitted", "Approved", "Reimbursement Recorded"])).limit(1))
    if dup:
        flags.append({"rule": "possible_duplicate_claim", "action": "flag"})
    return flags


@router.put("/expenses/{claim_id}", response_model=ExpenseRead)
def update_expense(claim_id: str, payload: ExpenseUpdate, db: Db, principal: Annotated[Principal, Depends(require_permission("expense:claim:write"))],
                   x_correlation_id: Annotated[str | None, Header()] = None):
    """Owner edits a Draft or Rejected claim before (re)submitting it."""
    row = owned_expense(db, claim_id, principal.organization_id)
    if row.employee_subject != principal.subject or row.status not in {"Draft", "Rejected"}:
        raise HTTPException(status_code=409, detail="Only the owner can edit a Draft or Rejected claim")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    for field in ("expense_date", "category_code", "merchant", "description", "amount", "receipt_reference", "project_reference"):
        setattr(row, field, getattr(payload, field))
    row.policy_flags = None
    audit(db, principal, "expense.updated", "expense_claim", row.id, {"amount": str(row.amount), "currency": row.currency}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


@router.put("/timesheets/{timesheet_id}", response_model=TimesheetRead)
def update_timesheet(timesheet_id: str, payload: TimesheetUpdate, db: Db, principal: Annotated[Principal, Depends(require_permission("tms:timesheet:write"))],
                     x_correlation_id: Annotated[str | None, Header()] = None):
    """Owner replaces the entries of a Draft or Rejected timesheet before (re)submitting it."""
    row = owned_timesheet(db, timesheet_id, principal.organization_id)
    if row.employee_subject != principal.subject or row.status not in {"Draft", "Rejected"}:
        raise HTTPException(status_code=409, detail="Only the owner can edit a Draft or Rejected timesheet")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "version_conflict", "current_version": row.version})
    check_timesheet_rules(db, principal.organization_id, principal.subject, payload.period_start, payload.period_end, payload.entries, exclude_id=row.id)
    db.query(TimeEntry).filter(TimeEntry.timesheet_id == row.id).delete(synchronize_session=False)
    for entry in payload.entries:
        db.add(TimeEntry(organization_id=principal.organization_id, timesheet_id=row.id, work_date=entry.work_date, project_reference=entry.project_reference,
                         task_reference=entry.task_reference, description=entry.description, hours=entry.hours, billable=entry.billable))
    row.period_start, row.period_end = payload.period_start, payload.period_end
    row.total_hours = sum((e.hours for e in payload.entries), start=0)
    audit(db, principal, "timesheet.updated", "timesheet", row.id, {"total_hours": str(row.total_hours), "entry_count": len(payload.entries)}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return row


# ---- expense policy rules (owner values; maker-checker) -------------------------------------------------------------

def dump_rule(r: ExpensePolicyRule) -> dict:
    return {"category_code": r.category_code, "currency": r.currency, "max_amount": str(r.max_amount) if r.max_amount is not None else None,
            "receipt_required_above": str(r.receipt_required_above) if r.receipt_required_above is not None else None, "on_violation": r.on_violation,
            "status": r.status, "enforced": r.status == "Approved", "updated_by": r.updated_by, "approved_by": r.approved_by}


@router.get("/expense-policies")
def list_expense_policies(db: Db, principal: Annotated[Principal, Depends(require_permission("expense:policy:read"))]):
    rows = db.scalars(select(ExpensePolicyRule).where(ExpensePolicyRule.organization_id == principal.organization_id).order_by(ExpensePolicyRule.category_code)).all()
    return {"rules": [dump_rule(r) for r in rows], "note": "BLOCKED - OWNER: limit values are owner policy. A rule is enforced only once approved by someone other than its maker."}


@router.put("/expense-policies/{category_code}")
def put_expense_policy(category_code: str, payload: PolicyRuleWrite, db: Db, principal: Annotated[Principal, Depends(require_permission("expense:policy:write"))],
                       x_correlation_id: Annotated[str | None, Header()] = None):
    if payload.max_amount is None and payload.receipt_required_above is None:
        raise HTTPException(status_code=422, detail={"code": "rule_has_no_limit"})
    row = db.scalar(select(ExpensePolicyRule).where(ExpensePolicyRule.organization_id == principal.organization_id, ExpensePolicyRule.category_code == category_code))
    if not row:
        row = ExpensePolicyRule(organization_id=principal.organization_id, category_code=category_code, currency=payload.currency, updated_by=principal.subject)
        db.add(row)
    row.currency, row.max_amount, row.receipt_required_above, row.on_violation = payload.currency, payload.max_amount, payload.receipt_required_above, payload.on_violation
    row.status, row.updated_by, row.approved_by, row.approved_at = "Pending Approval", principal.subject, None, None
    db.flush()
    audit(db, principal, "expense_policy.updated", "expense_policy", row.id, {"category_code": category_code}, x_correlation_id)
    db.commit()
    return dump_rule(row)


@router.post("/expense-policies/{category_code}/approve")
def approve_expense_policy(category_code: str, db: Db, principal: Annotated[Principal, Depends(require_permission("expense:policy:approve"))],
                           x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(ExpensePolicyRule).where(ExpensePolicyRule.organization_id == principal.organization_id, ExpensePolicyRule.category_code == category_code))
    if not row:
        raise HTTPException(status_code=404, detail="Expense policy rule not found")
    if row.status == "Approved":
        raise HTTPException(status_code=409, detail={"code": "policy_already_approved"})
    if row.updated_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_approve_own_policy"})
    row.status, row.approved_by, row.approved_at = "Approved", principal.subject, datetime.now(timezone.utc)
    audit(db, principal, "expense_policy.approved", "expense_policy", row.id, {"category_code": category_code}, x_correlation_id)
    db.commit()
    return dump_rule(row)
