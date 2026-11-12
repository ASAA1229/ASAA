from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from asaa_ap.database import get_db
from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, require_permission
from asaa_people.models import Employee, EmploymentRecord

router = APIRouter(prefix="/api/v1/hr", tags=["Human Resources"])
Db = Annotated[Session, Depends(get_db)]


class EmployeeProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_code: str | None = Field(default=None, max_length=64)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    work_email: str | None = Field(default=None, max_length=320)
    work_phone: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be supplied")
        return self


class EmployeeLifecycleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(min_length=1, max_length=32)
    effective_from: date
    reason: str = Field(min_length=1, max_length=2000)


LIFECYCLE_STATES = {"Preboarding", "Active", "On Leave", "Suspended", "Offboarding", "Inactive"}


def get_employee(db: Session, employee_id: str, organization_id: str) -> Employee:
    employee = db.scalar(select(Employee).where(
        Employee.id == employee_id,
        Employee.organization_id == organization_id,
    ))
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def serialize(row):
    return {key: value for key, value in row.__dict__.items() if not key.startswith("_")}


@router.patch("/employees/{employee_id}")
def update_employee_profile(
    employee_id: str,
    payload: EmployeeProfilePatch,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employee:write"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    employee = get_employee(db, employee_id, principal.organization_id)
    changes = payload.model_dump(exclude_unset=True)
    if "employee_code" in changes and changes["employee_code"]:
        duplicate = db.scalar(select(Employee.id).where(
            Employee.organization_id == principal.organization_id,
            Employee.employee_code == changes["employee_code"],
            Employee.id != employee.id,
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail={"code": "employee_code_exists"})
    for field, value in changes.items():
        setattr(employee, field, value)
    db.add(AuditEvent(
        organization_id=principal.organization_id,
        actor_id=principal.subject,
        action="employee.profile_updated",
        entity_type="hr_employee",
        entity_id=employee.id,
        details={"changed_fields": sorted(changes)},
        correlation_id=x_correlation_id,
    ))
    db.commit()
    db.refresh(employee)
    return serialize(employee)


@router.post("/employees/{employee_id}/lifecycle", status_code=201)
def change_employee_lifecycle(
    employee_id: str,
    payload: EmployeeLifecycleChange,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("hr:employee:lifecycle"))],
    x_correlation_id: Annotated[str | None, Header()] = None,
):
    if payload.status not in LIFECYCLE_STATES:
        raise HTTPException(status_code=422, detail={
            "code": "unsupported_lifecycle_status",
            "allowed": sorted(LIFECYCLE_STATES),
        })
    employee = get_employee(db, employee_id, principal.organization_id)
    if payload.status == employee.status:
        raise HTTPException(status_code=409, detail={"code": "lifecycle_status_unchanged"})

    latest = db.scalar(select(EmploymentRecord).where(
        EmploymentRecord.organization_id == principal.organization_id,
        EmploymentRecord.employee_id == employee.id,
    ).order_by(EmploymentRecord.effective_from.desc()).limit(1))
    if latest and payload.effective_from <= latest.effective_from:
        raise HTTPException(status_code=409, detail={
            "code": "lifecycle_effective_date_must_follow_latest_record",
            "latest_effective_from": latest.effective_from.isoformat(),
        })

    if latest and latest.effective_to is None:
        from datetime import timedelta
        latest.effective_to = payload.effective_from - timedelta(days=1)

    record = EmploymentRecord(
        organization_id=principal.organization_id,
        employee_id=employee.id,
        department_id=latest.department_id if latest else None,
        position_title=latest.position_title if latest else None,
        manager_employee_id=latest.manager_employee_id if latest else None,
        work_location=latest.work_location if latest else None,
        employment_type=latest.employment_type if latest else employee.employment_type,
        status=payload.status,
        effective_from=payload.effective_from,
        reason=payload.reason,
        created_by=principal.subject,
    )
    employee.status = payload.status
    db.add(record)
    db.add(AuditEvent(
        organization_id=principal.organization_id,
        actor_id=principal.subject,
        action="employee.lifecycle_changed",
        entity_type="hr_employee",
        entity_id=employee.id,
        details={
            "previous_status": latest.status if latest else "Preboarding",
            "new_status": payload.status,
            "effective_from": payload.effective_from.isoformat(),
            "reason": payload.reason,
            "employment_record_id": record.id,
        },
        correlation_id=x_correlation_id,
    ))
    db.commit()
    db.refresh(record)
    return serialize(record)
