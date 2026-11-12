from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_people.models import (
    Employee, EmploymentRecord, EmployeeDocument, EmployeeAsset, LeaveRequest,
    EmployeeExitCase, OnboardingTemplate, OnboardingTask, OnboardingAssignment,
    CompensationRecord, PayrollRun, PayrollEntry, PayrollPeriod,
)
from asaa_people.schemas import (
    EmployeeDocumentCreate, EmployeeAssetCreate, EmployeeAssetReturn,
    LeaveRequestCreate, LeaveRequestReview, EmployeeExitCreate,
    OnboardingTemplateStatusUpdate, OnboardingTaskAssignment,
    CompensationDecision, PayrollRunReview,
)

router = APIRouter(tags=["People Operations"])
Db = Annotated[Session, Depends(get_db)]


def now():
    return datetime.now(timezone.utc)


def serialize(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


def audit(db, principal, action, entity_type, entity_id, details, correlation_id):
    db.add(AuditEvent(
        organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id,
    ))


def employee_or_404(db, employee_id, org_id):
    row = db.scalar(select(Employee).where(
        Employee.id == employee_id, Employee.organization_id == org_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    return row


@router.post("/api/v1/hr/employees/{employee_id}/documents", status_code=201)
def add_employee_document(employee_id: str, payload: EmployeeDocumentCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:document:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee_or_404(db, employee_id, principal.organization_id)
    row = EmployeeDocument(
        organization_id=principal.organization_id, employee_id=employee_id,
        created_by=principal.subject, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, principal, "employee_document.registered", "hr_employee_document", row.id,
          {"document_type": row.document_type, "classification": row.classification},
          x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/api/v1/hr/employees/{employee_id}/documents")
def list_employee_documents(employee_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:document:read"))]):
    employee_or_404(db, employee_id, principal.organization_id)
    rows = db.scalars(select(EmployeeDocument).where(
        EmployeeDocument.organization_id == principal.organization_id,
        EmployeeDocument.employee_id == employee_id,
        EmployeeDocument.status == "Active",
    ).order_by(EmployeeDocument.created_at.desc())).all()
    return [serialize(row) for row in rows]


@router.post("/api/v1/hr/employees/{employee_id}/assets", status_code=201)
def issue_employee_asset(employee_id: str, payload: EmployeeAssetCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:asset:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee_or_404(db, employee_id, principal.organization_id)
    duplicate = db.scalar(select(EmployeeAsset.id).where(
        EmployeeAsset.organization_id == principal.organization_id,
        EmployeeAsset.asset_reference == payload.asset_reference,
        EmployeeAsset.status == "Issued",
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail={"code": "asset_already_issued"})
    row = EmployeeAsset(
        organization_id=principal.organization_id, employee_id=employee_id,
        created_by=principal.subject, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, principal, "employee_asset.issued", "hr_employee_asset", row.id,
          {"asset_reference": row.asset_reference, "asset_type": row.asset_type}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/api/v1/hr/employees/{employee_id}/assets")
def list_employee_assets(employee_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:asset:read"))]):
    employee_or_404(db, employee_id, principal.organization_id)
    rows = db.scalars(select(EmployeeAsset).where(
        EmployeeAsset.organization_id == principal.organization_id,
        EmployeeAsset.employee_id == employee_id,
    ).order_by(EmployeeAsset.issued_on.desc())).all()
    return [serialize(row) for row in rows]


@router.post("/api/v1/hr/assets/{asset_id}/return")
def return_employee_asset(asset_id: str, payload: EmployeeAssetReturn, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:asset:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(EmployeeAsset).where(
        EmployeeAsset.id == asset_id, EmployeeAsset.organization_id == principal.organization_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Asset assignment not found")
    if row.status != "Issued":
        raise HTTPException(status_code=409, detail={"code": "asset_not_issued"})
    if payload.returned_on < row.issued_on:
        raise HTTPException(status_code=422, detail={"code": "return_before_issue"})
    row.returned_on = payload.returned_on
    row.condition_on_return = payload.condition_on_return
    row.status = "Returned"
    audit(db, principal, "employee_asset.returned", "hr_employee_asset", row.id,
          {"returned_on": row.returned_on.isoformat()}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/api/v1/hr/employees/{employee_id}/leave-requests", status_code=201)
def create_leave_request(employee_id: str, payload: LeaveRequestCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:leave:request"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee_or_404(db, employee_id, principal.organization_id)
    overlap = db.scalar(select(LeaveRequest.id).where(
        LeaveRequest.organization_id == principal.organization_id,
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["Submitted", "Approved"]),
        LeaveRequest.start_date <= payload.end_date,
        LeaveRequest.end_date >= payload.start_date,
    ))
    if overlap:
        raise HTTPException(status_code=409, detail={"code": "leave_request_overlap"})
    row = LeaveRequest(
        organization_id=principal.organization_id, employee_id=employee_id,
        created_by=principal.subject, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, principal, "leave_request.submitted", "hr_leave_request", row.id,
          {"start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat()},
          x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/api/v1/hr/leave-requests")
def list_leave_requests(db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:leave:read"))],
    employee_id: str | None = None, status: str | None = None):
    stmt = select(LeaveRequest).where(LeaveRequest.organization_id == principal.organization_id)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    rows = db.scalars(stmt.order_by(LeaveRequest.created_at.desc())).all()
    return [serialize(row) for row in rows]


@router.post("/api/v1/hr/leave-requests/{request_id}/review")
def review_leave_request(request_id: str, payload: LeaveRequestReview, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:leave:review"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(LeaveRequest).where(
        LeaveRequest.id == request_id, LeaveRequest.organization_id == principal.organization_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if row.status != "Submitted":
        raise HTTPException(status_code=409, detail={"code": "leave_request_not_reviewable"})
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_review_own_request"})
    row.status = payload.decision
    row.reviewer_subject = principal.subject
    row.reviewed_at = now()
    row.review_note = payload.review_note
    audit(db, principal, "leave_request.reviewed", "hr_leave_request", row.id,
          {"decision": row.status}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/api/v1/hr/employees/{employee_id}/exit-cases", status_code=201)
def create_exit_case(employee_id: str, payload: EmployeeExitCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:exit:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee = employee_or_404(db, employee_id, principal.organization_id)
    if employee.status in {"Inactive", "Offboarding"}:
        raise HTTPException(status_code=409, detail={"code": "employee_exit_already_started_or_complete"})
    if payload.planned_last_day < date.today():
        raise HTTPException(status_code=422, detail={"code": "planned_last_day_in_past"})
    existing = db.scalar(select(EmployeeExitCase.id).where(
        EmployeeExitCase.organization_id == principal.organization_id,
        EmployeeExitCase.employee_id == employee_id,
        EmployeeExitCase.status == "Open",
    ))
    if existing:
        raise HTTPException(status_code=409, detail={"code": "open_exit_case_exists"})
    latest = db.scalar(select(EmploymentRecord).where(
        EmploymentRecord.organization_id == principal.organization_id,
        EmploymentRecord.employee_id == employee_id,
    ).order_by(EmploymentRecord.effective_from.desc()).limit(1))
    if latest and payload.planned_last_day < latest.effective_from:
        raise HTTPException(status_code=409, detail={"code": "last_day_precedes_latest_employment_record"})
    row = EmployeeExitCase(
        organization_id=principal.organization_id, employee_id=employee_id,
        created_by=principal.subject, **payload.model_dump(),
    )
    db.add(row)
    if latest and latest.effective_to is None:
        latest.effective_to = payload.planned_last_day - timedelta(days=1)
    history = EmploymentRecord(
        organization_id=principal.organization_id, employee_id=employee_id,
        department_id=latest.department_id if latest else None,
        position_title=latest.position_title if latest else None,
        manager_employee_id=latest.manager_employee_id if latest else None,
        work_location=latest.work_location if latest else None,
        employment_type=latest.employment_type if latest else employee.employment_type,
        status="Offboarding", effective_from=payload.planned_last_day,
        reason="Offboarding case opened", created_by=principal.subject,
    )
    employee.status = "Offboarding"
    db.add(history)
    db.flush()
    audit(db, principal, "employee_exit.opened", "hr_employee_exit_case", row.id,
          {"planned_last_day": row.planned_last_day.isoformat()}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/api/v1/hr/exit-cases")
def list_exit_cases(db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:exit:read"))],
    employee_id: str | None = None):
    stmt = select(EmployeeExitCase).where(EmployeeExitCase.organization_id == principal.organization_id)
    if employee_id:
        stmt = stmt.where(EmployeeExitCase.employee_id == employee_id)
    rows = db.scalars(stmt.order_by(EmployeeExitCase.created_at.desc())).all()
    return [serialize(row) for row in rows]


@router.post("/api/v1/hr/exit-cases/{case_id}/complete")
def complete_exit_case(case_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:exit:complete"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    case = db.scalar(select(EmployeeExitCase).where(
        EmployeeExitCase.id == case_id, EmployeeExitCase.organization_id == principal.organization_id
    ))
    if not case:
        raise HTTPException(status_code=404, detail="Exit case not found")
    if case.status != "Open":
        raise HTTPException(status_code=409, detail={"code": "exit_case_not_open"})
    if date.today() < case.planned_last_day:
        raise HTTPException(status_code=409, detail={"code": "planned_last_day_not_reached"})
    outstanding = db.scalar(select(func.count(EmployeeAsset.id)).where(
        EmployeeAsset.organization_id == principal.organization_id,
        EmployeeAsset.employee_id == case.employee_id,
        EmployeeAsset.status == "Issued",
    )) or 0
    if outstanding:
        raise HTTPException(status_code=409, detail={
            "code": "outstanding_assets", "count": outstanding
        })
    employee = employee_or_404(db, case.employee_id, principal.organization_id)
    latest = db.scalar(select(EmploymentRecord).where(
        EmploymentRecord.organization_id == principal.organization_id,
        EmploymentRecord.employee_id == employee.id,
    ).order_by(EmploymentRecord.effective_from.desc()).limit(1))
    if latest and date.today() < latest.effective_from:
        raise HTTPException(status_code=409, detail={"code": "exit_history_effective_date_conflict"})
    if latest and latest.effective_from == date.today():
        latest.status = "Inactive"
        latest.reason = "Offboarding completed"
    else:
        if latest and latest.effective_to is None:
            latest.effective_to = date.today() - timedelta(days=1)
        history = EmploymentRecord(
            organization_id=principal.organization_id, employee_id=employee.id,
            department_id=latest.department_id if latest else None,
            position_title=latest.position_title if latest else None,
            manager_employee_id=latest.manager_employee_id if latest else None,
            work_location=latest.work_location if latest else None,
            employment_type=latest.employment_type if latest else employee.employment_type,
            status="Inactive", effective_from=date.today(),
            reason="Offboarding completed", created_by=principal.subject,
        )
        db.add(history)
    employee.status = "Inactive"
    case.status = "Completed"
    case.completed_at = now()
    case.completed_by = principal.subject
    db.flush()
    audit(db, principal, "employee_exit.completed", "hr_employee_exit_case", case.id,
          {"employee_id": employee.id, "status": employee.status}, x_correlation_id)
    db.commit()
    db.refresh(case)
    return serialize(case)


@router.patch("/api/v1/onboarding/templates/{template_id}/status")
def update_onboarding_template_status(template_id: str, payload: OnboardingTemplateStatusUpdate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:template:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(OnboardingTemplate).where(
        OnboardingTemplate.id == template_id,
        OnboardingTemplate.organization_id == principal.organization_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Onboarding template not found")
    row.active = payload.active
    audit(db, principal, "onboarding_template.status_changed", "onboarding_template", row.id,
          {"active": row.active}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.patch("/api/v1/onboarding/tasks/{task_id}/assignee")
def assign_onboarding_task(task_id: str, payload: OnboardingTaskAssignment, db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:task:assign"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(OnboardingTask).where(
        OnboardingTask.id == task_id, OnboardingTask.organization_id == principal.organization_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Onboarding task not found")
    if row.status in {"Completed", "Waived"}:
        raise HTTPException(status_code=409, detail={"code": "completed_task_not_assignable"})
    row.assigned_to = payload.assigned_to
    row.assigned_at = now() if payload.assigned_to else None
    audit(db, principal, "onboarding_task.assigned", "onboarding_task", row.id,
          {"assigned_to": row.assigned_to}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post("/api/v1/payroll/compensation/{record_id}/decision")
def decide_compensation(record_id: str, payload: CompensationDecision, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:compensation:approve"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = db.scalar(select(CompensationRecord).where(
        CompensationRecord.id == record_id,
        CompensationRecord.organization_id == principal.organization_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Compensation record not found")
    if row.status != "Pending Approval":
        raise HTTPException(status_code=409, detail={"code": "compensation_not_pending"})
    if row.created_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_approve_own_compensation"})
    if payload.decision == "Approved":
        overlap = db.scalar(select(CompensationRecord.id).where(
            CompensationRecord.organization_id == principal.organization_id,
            CompensationRecord.employee_id == row.employee_id,
            CompensationRecord.id != row.id,
            CompensationRecord.status == "Approved",
            CompensationRecord.effective_from <= (row.effective_to or date.max),
            (CompensationRecord.effective_to >= row.effective_from) | (
                CompensationRecord.effective_to.is_(None)
                & (CompensationRecord.effective_from >= row.effective_from)
            ),
        ))
        if overlap:
            raise HTTPException(status_code=409, detail={"code": "approved_compensation_period_overlap"})
        previous = db.scalars(select(CompensationRecord).where(
            CompensationRecord.organization_id == principal.organization_id,
            CompensationRecord.employee_id == row.employee_id,
            CompensationRecord.status == "Approved",
            CompensationRecord.effective_from < row.effective_from,
            CompensationRecord.effective_to.is_(None),
        )).all()
        for item in previous:
            item.effective_to = row.effective_from - timedelta(days=1)
    row.status = payload.decision
    row.approved_by = principal.subject
    row.approved_at = now()
    row.approval_note = payload.approval_note
    audit(db, principal, "compensation.decided", "pay_compensation_record", row.id,
          {"decision": row.status}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/api/v1/payroll/runs/{run_id}/summary")
def payroll_run_summary(run_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:read"))]):
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    rows = db.scalars(select(PayrollEntry).where(
        PayrollEntry.organization_id == principal.organization_id, PayrollEntry.run_id == run_id
    )).all()
    return {
        "run_id": run.id, "run_code": run.run_code, "status": run.status,
        "currency": run.currency, "entry_count": len(rows),
        "gross_total": str(sum((row.gross_amount for row in rows), Decimal("0.00"))),
        "deduction_total": str(sum((row.deduction_total for row in rows), Decimal("0.00"))),
        "net_total": str(sum((row.net_amount for row in rows), Decimal("0.00"))),
        "entries_reconciled": all(row.gross_amount - row.deduction_total == row.net_amount for row in rows),
    }


@router.post("/api/v1/payroll/runs/{run_id}/submit")
def submit_payroll_run(run_id: str, payload: PayrollRunReview, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:run:submit"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status not in {"Draft", "Changes Requested"}:
        raise HTTPException(status_code=409, detail={"code": "payroll_run_not_submittable"})
    count = db.scalar(select(func.count(PayrollEntry.id)).where(
        PayrollEntry.organization_id == principal.organization_id, PayrollEntry.run_id == run_id
    )) or 0
    if count == 0:
        raise HTTPException(status_code=409, detail={"code": "payroll_run_empty"})
    run.status = "In Review"
    run.submitted_at = now()
    run.review_note = payload.review_note
    audit(db, principal, "payroll_run.submitted", "payroll_run", run.id,
          {"entry_count": count}, x_correlation_id)
    db.commit()
    db.refresh(run)
    return serialize(run)


@router.post("/api/v1/payroll/runs/{run_id}/decision")
def decide_payroll_run(run_id: str, payload: CompensationDecision, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:run:approve"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != "In Review":
        raise HTTPException(status_code=409, detail={"code": "payroll_run_not_in_review"})
    if run.created_by == principal.subject:
        raise HTTPException(status_code=403, detail={"code": "maker_cannot_approve_own_run"})
    if payload.decision == "Approved":
        run.status = "Approved"
        run.approved_by = principal.subject
        run.approved_at = now()
    else:
        run.status = "Changes Requested"
        run.approved_by = None
        run.approved_at = None
    run.review_note = payload.approval_note
    audit(db, principal, "payroll_run.reviewed", "payroll_run", run.id,
          {"decision": payload.decision}, x_correlation_id)
    db.commit()
    db.refresh(run)
    return serialize(run)


@router.post("/api/v1/payroll/runs/{run_id}/close")
def close_payroll_run(run_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:run:close"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status != "Approved":
        raise HTTPException(status_code=409, detail={"code": "payroll_run_not_approved"})
    run.status = "Closed"
    run.closed_at = now()
    audit(db, principal, "payroll_run.closed", "payroll_run", run.id,
          {"approved_by": run.approved_by}, x_correlation_id)
    db.commit()
    db.refresh(run)
    return serialize(run)
