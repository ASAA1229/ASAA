from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_workforce_finance.models import Timesheet, TimeEntry, ExpenseClaim
from asaa_workforce_finance.schemas import (TimesheetCreate, TimesheetRead, TimesheetReview, ExpenseCreate, ExpenseRead, ExpenseReview, ExpenseReimbursement)

router = APIRouter(prefix="/api/v1/workforce-finance", tags=["Timesheets and Expenses"])
Db = Annotated[Session, Depends(get_db)]

def audit(db, principal, action, kind, entity_id, details, correlation_id):
    db.add(AuditEvent(organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=kind, entity_id=entity_id, details=details,
        correlation_id=correlation_id))

def owned_timesheet(db, timesheet_id, org):
    row = db.scalar(select(Timesheet).where(Timesheet.id == timesheet_id, Timesheet.organization_id == org))
    if not row:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return row

def owned_expense(db, claim_id, org):
    row = db.scalar(select(ExpenseClaim).where(ExpenseClaim.id == claim_id, ExpenseClaim.organization_id == org))
    if not row:
        raise HTTPException(status_code=404, detail="Expense claim not found")
    return row

@router.post("/timesheets", response_model=TimesheetRead, status_code=201)
def create_timesheet(payload: TimesheetCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("tms:timesheet:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
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
    row.status, row.review_reason = "Submitted", payload.reason
    audit(db, principal, "expense.submitted", "expense_claim", row.id, {}, x_correlation_id)
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
    row.status = "Approved" if payload.reason.lower().startswith("approve:") else "Rejected"
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
