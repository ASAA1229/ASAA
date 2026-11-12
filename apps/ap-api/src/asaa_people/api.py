from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_people.models import (
    Employee, EmploymentRecord, OnboardingTemplate, OnboardingTaskTemplate,
    OnboardingAssignment, OnboardingTask, CompensationRecord, PayrollPeriod,
    PayrollRun, PayrollEntry,
)
from asaa_people.schemas import (
    EmployeeCreate, EmploymentRecordCreate, OnboardingTemplateCreate,
    OnboardingAssignmentCreate, OnboardingTaskUpdate, CompensationCreate,
    PayrollPeriodCreate, PayrollRunCreate, PayrollEntryCreate,
)

Db = Annotated[Session, Depends(get_db)]
hr_router = APIRouter(prefix="/api/v1/hr", tags=["Human Resources"])
onboarding_router = APIRouter(prefix="/api/v1/onboarding", tags=["Employee Onboarding"])
payroll_router = APIRouter(prefix="/api/v1/payroll", tags=["Salaries and Payroll"])


def audit(db: Session, principal: Principal, action: str, entity_type: str,
          entity_id: str, details: dict, correlation_id: str | None):
    db.add(AuditEvent(
        organization_id=principal.organization_id, actor_id=principal.subject,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, correlation_id=correlation_id,
    ))


def view(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


def employee_or_404(db: Session, employee_id: str, org_id: str):
    row = db.scalar(select(Employee).where(
        Employee.id == employee_id, Employee.organization_id == org_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    return row


@hr_router.post("/employees", status_code=201)
def create_employee(payload: EmployeeCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employee:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    if payload.employee_code:
        duplicate = db.scalar(select(Employee.id).where(
            Employee.organization_id == principal.organization_id,
            Employee.employee_code == payload.employee_code
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail={"code": "employee_code_exists"})
    row = Employee(
        organization_id=principal.organization_id, **payload.model_dump(),
        status="Preboarding", created_by=principal.subject,
    )
    db.add(row)
    db.flush()
    audit(db, principal, "employee.created", "hr_employee", row.id,
          {"status": row.status, "employment_type": row.employment_type}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@hr_router.get("/employees")
def list_employees(db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employee:read"))],
    status: str | None = None, limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0)):
    stmt = select(Employee).where(Employee.organization_id == principal.organization_id)
    if status:
        stmt = stmt.where(Employee.status == status)
    rows = db.scalars(stmt.order_by(Employee.created_at.desc()).offset(offset).limit(limit)).all()
    return [view(row) for row in rows]


@hr_router.get("/employees/{employee_id}")
def get_employee(employee_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employee:read"))]):
    return view(employee_or_404(db, employee_id, principal.organization_id))


@hr_router.post("/employees/{employee_id}/employment-records", status_code=201)
def add_employment_record(employee_id: str, payload: EmploymentRecordCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employment:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee_or_404(db, employee_id, principal.organization_id)
    if payload.manager_employee_id:
        employee_or_404(db, payload.manager_employee_id, principal.organization_id)
    row = EmploymentRecord(
        organization_id=principal.organization_id, employee_id=employee_id,
        created_by=principal.subject, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, principal, "employment_record.created", "hr_employment_record", row.id,
          {"effective_from": payload.effective_from.isoformat()}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@hr_router.get("/employees/{employee_id}/employment-records")
def employment_history(employee_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employee:read"))]):
    employee_or_404(db, employee_id, principal.organization_id)
    rows = db.scalars(select(EmploymentRecord).where(
        EmploymentRecord.organization_id == principal.organization_id,
        EmploymentRecord.employee_id == employee_id
    ).order_by(EmploymentRecord.effective_from.desc())).all()
    return [view(row) for row in rows]


@onboarding_router.post("/templates", status_code=201)
def create_onboarding_template(payload: OnboardingTemplateCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:template:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = OnboardingTemplate(
        organization_id=principal.organization_id, template_code=payload.template_code,
        name=payload.name, description=payload.description,
        employment_type=payload.employment_type, created_by=principal.subject,
    )
    db.add(row)
    db.flush()
    for task in payload.tasks:
        db.add(OnboardingTaskTemplate(template_id=row.id, **task.model_dump()))
    audit(db, principal, "onboarding_template.created", "onboarding_template", row.id,
          {"task_count": len(payload.tasks)}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@onboarding_router.get("/templates")
def list_onboarding_templates(db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:read"))]):
    rows = db.scalars(select(OnboardingTemplate).where(
        OnboardingTemplate.organization_id == principal.organization_id
    ).order_by(OnboardingTemplate.name)).all()
    result = []
    for row in rows:
        item = view(row)
        tasks = db.scalars(select(OnboardingTaskTemplate).where(
            OnboardingTaskTemplate.template_id == row.id
        ).order_by(OnboardingTaskTemplate.sequence)).all()
        item["tasks"] = [view(task) for task in tasks]
        result.append(item)
    return result


@onboarding_router.post("/assignments", status_code=201)
def assign_onboarding(payload: OnboardingAssignmentCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:assignment:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee_or_404(db, payload.employee_id, principal.organization_id)
    template = db.scalar(select(OnboardingTemplate).where(
        OnboardingTemplate.id == payload.template_id,
        OnboardingTemplate.organization_id == principal.organization_id,
        OnboardingTemplate.active.is_(True),
    ))
    if not template:
        raise HTTPException(status_code=404, detail="Active onboarding template not found")
    duplicate = db.scalar(select(OnboardingAssignment.id).where(
        OnboardingAssignment.organization_id == principal.organization_id,
        OnboardingAssignment.employee_id == payload.employee_id,
        OnboardingAssignment.template_id == payload.template_id,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail={"code": "onboarding_assignment_exists"})
    assignment = OnboardingAssignment(
        organization_id=principal.organization_id, employee_id=payload.employee_id,
        template_id=payload.template_id, target_date=payload.target_date,
        created_by=principal.subject,
    )
    db.add(assignment)
    db.flush()
    templates = db.scalars(select(OnboardingTaskTemplate).where(
        OnboardingTaskTemplate.template_id == template.id
    ).order_by(OnboardingTaskTemplate.sequence)).all()
    if not any(task.required for task in templates):
        assignment.status = "Completed"
    for task in templates:
        db.add(OnboardingTask(
            organization_id=principal.organization_id, assignment_id=assignment.id,
            source_task_id=task.id, title=task.title, description=task.description, owner_role=task.owner_role,
            required=task.required, status="Pending",
        ))
    audit(db, principal, "onboarding.assigned", "onboarding_assignment", assignment.id,
          {"employee_id": payload.employee_id, "task_count": len(templates)}, x_correlation_id)
    db.commit()
    db.refresh(assignment)
    return view(assignment)


@onboarding_router.get("/assignments")
def list_onboarding_assignments(db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:read"))],
    employee_id: str | None = None):
    stmt = select(OnboardingAssignment).where(
        OnboardingAssignment.organization_id == principal.organization_id
    )
    if employee_id:
        stmt = stmt.where(OnboardingAssignment.employee_id == employee_id)
    rows = db.scalars(stmt.order_by(OnboardingAssignment.created_at.desc())).all()
    result = []
    for row in rows:
        item = view(row)
        tasks = db.scalars(select(OnboardingTask).where(
            OnboardingTask.organization_id == principal.organization_id,
            OnboardingTask.assignment_id == row.id
        )).all()
        item["tasks"] = [view(task) for task in tasks]
        result.append(item)
    return result


@onboarding_router.patch("/tasks/{task_id}")
def update_onboarding_task(task_id: str, payload: OnboardingTaskUpdate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("onboarding:task:update"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    task = db.scalar(select(OnboardingTask).where(
        OnboardingTask.id == task_id,
        OnboardingTask.organization_id == principal.organization_id,
    ))
    if not task:
        raise HTTPException(status_code=404, detail="Onboarding task not found")
    task.status = payload.status
    if "evidence_reference" in payload.model_fields_set:
        task.evidence_reference = payload.evidence_reference
    if "due_date" in payload.model_fields_set:
        task.due_date = payload.due_date
    task.completed_at = datetime.now(timezone.utc) if payload.status == "Completed" else None
    task.completed_by = principal.subject if payload.status == "Completed" else None
    tasks = db.scalars(select(OnboardingTask).where(
        OnboardingTask.assignment_id == task.assignment_id
    )).all()
    required = [item for item in tasks if item.required]
    assignment = db.get(OnboardingAssignment, task.assignment_id)
    if all(item.status in {"Completed", "Waived"} for item in required):
        assignment.status = "Completed"
    elif any(item.status == "Blocked" for item in tasks):
        assignment.status = "Blocked"
    else:
        assignment.status = "In Progress"
    audit(db, principal, "onboarding_task.updated", "onboarding_task", task.id,
          {"status": task.status, "due_date": task.due_date.isoformat() if task.due_date else None,
           "assignment_status": assignment.status}, x_correlation_id)
    db.commit()
    db.refresh(task)
    return view(task)


@payroll_router.post("/compensation", status_code=201)
def create_compensation(payload: CompensationCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:compensation:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    employee_or_404(db, payload.employee_id, principal.organization_id)
    row = CompensationRecord(
        organization_id=principal.organization_id, **payload.model_dump(),
        created_by=principal.subject,
    )
    db.add(row)
    db.flush()
    audit(db, principal, "compensation.created", "pay_compensation_record", row.id,
          {"employee_id": row.employee_id, "effective_from": row.effective_from.isoformat(),
           "status": row.status}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@payroll_router.get("/compensation")
def list_compensation(employee_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:compensation:read"))]):
    employee_or_404(db, employee_id, principal.organization_id)
    rows = db.scalars(select(CompensationRecord).where(
        CompensationRecord.organization_id == principal.organization_id,
        CompensationRecord.employee_id == employee_id
    ).order_by(CompensationRecord.effective_from.desc())).all()
    return [view(row) for row in rows]


@payroll_router.post("/periods", status_code=201)
def create_payroll_period(payload: PayrollPeriodCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:period:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    row = PayrollPeriod(organization_id=principal.organization_id,
                        created_by=principal.subject, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, principal, "payroll_period.created", "payroll_period", row.id,
          {"period_code": row.period_code}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@payroll_router.get("/periods")
def list_payroll_periods(db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:read"))]):
    rows = db.scalars(select(PayrollPeriod).where(
        PayrollPeriod.organization_id == principal.organization_id
    ).order_by(PayrollPeriod.start_date.desc())).all()
    return [view(row) for row in rows]


@payroll_router.post("/runs", status_code=201)
def create_payroll_run(payload: PayrollRunCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:run:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    period = db.scalar(select(PayrollPeriod).where(
        PayrollPeriod.id == payload.period_id,
        PayrollPeriod.organization_id == principal.organization_id,
    ))
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    if period.status != "Open":
        raise HTTPException(status_code=409, detail={"code": "payroll_period_not_open"})
    row = PayrollRun(organization_id=principal.organization_id,
                     created_by=principal.subject, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, principal, "payroll_run.created", "payroll_run", row.id,
          {"period_id": row.period_id, "status": row.status}, x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@payroll_router.get("/runs")
def list_payroll_runs(db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:read"))]):
    rows = db.scalars(select(PayrollRun).where(
        PayrollRun.organization_id == principal.organization_id
    ).order_by(PayrollRun.created_at.desc())).all()
    return [view(row) for row in rows]


@payroll_router.post("/runs/{run_id}/entries", status_code=201)
def add_payroll_entry(run_id: str, payload: PayrollEntryCreate, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:entry:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None):
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if run.status not in {"Draft", "Changes Requested"}:
        raise HTTPException(status_code=409, detail={"code": "payroll_run_not_editable"})
    employee_or_404(db, payload.employee_id, principal.organization_id)
    if payload.currency != run.currency:
        raise HTTPException(status_code=409, detail={"code": "payroll_currency_mismatch"})
    row = PayrollEntry(
        organization_id=principal.organization_id, run_id=run.id,
        created_by=principal.subject, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    audit(db, principal, "payroll_entry.created", "payroll_entry", row.id,
          {"run_id": run.id, "employee_id": row.employee_id, "currency": row.currency},
          x_correlation_id)
    db.commit()
    db.refresh(row)
    return view(row)


@payroll_router.get("/runs/{run_id}/entries")
def list_payroll_entries(run_id: str, db: Db,
    principal: Annotated[Principal, Depends(require_permission("payroll:read"))]):
    run = db.scalar(select(PayrollRun).where(
        PayrollRun.id == run_id, PayrollRun.organization_id == principal.organization_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    rows = db.scalars(select(PayrollEntry).where(
        PayrollEntry.organization_id == principal.organization_id,
        PayrollEntry.run_id == run_id
    )).all()
    return [view(row) for row in rows]
