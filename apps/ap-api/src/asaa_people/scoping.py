"""Data-scope predicates for people records (D3.14). An employee's unit/department is the department_id of the employment record in force today."""
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select, true

from asaa_governance.scope import AccessScope
from asaa_people.models import Employee, EmploymentRecord, PayrollEntry, PayrollRun


def employee_unit_clause(org_id: str):
    def clause(ids):
        today = date.today()
        return Employee.id.in_(select(EmploymentRecord.employee_id).where(
            EmploymentRecord.organization_id == org_id, EmploymentRecord.department_id.in_(ids),
            EmploymentRecord.effective_from <= today, or_(EmploymentRecord.effective_to.is_(None), EmploymentRecord.effective_to >= today)))
    return clause


def employee_clause(scope: AccessScope, org_id: str):
    """Employees inside the scope: by unit/department of the current employment record, or by the employee record itself."""
    return scope.clause(unit=employee_unit_clause(org_id), record=Employee.id)


def payroll_entry_clause(scope: AccessScope, org_id: str):
    """Payroll entries inside the scope: through the employee's unit/department, or the entry record itself."""
    def by_unit(ids):
        return PayrollEntry.employee_id.in_(select(Employee.id).where(Employee.organization_id == org_id, employee_unit_clause(org_id)(ids)))
    return scope.clause(unit=by_unit, record=PayrollEntry.id)


def payroll_run_clause(scope: AccessScope, org_id: str):
    """Payroll runs the caller may see: with a restricted scope, only runs that hold at least one in-scope entry (the entries decide, a run has no unit of its own)."""
    if scope.unrestricted:
        return true()
    return PayrollRun.id.in_(select(PayrollEntry.run_id).where(PayrollEntry.organization_id == org_id, payroll_entry_clause(scope, org_id)))


def check_payroll_run_scope(db, run: PayrollRun, org_id: str, scope: AccessScope, whole: bool = False):
    """Run-level access follows the entries. A restricted caller sees a run only through its in-scope entries (404 when it has none) and
    may act on the whole run (submit, approve, close, calculate) only when every entry is in scope (403 otherwise). No-op when unrestricted."""
    if scope.unrestricted:
        return
    total = db.scalar(select(func.count(PayrollEntry.id)).where(PayrollEntry.organization_id == org_id, PayrollEntry.run_id == run.id)) or 0
    visible = db.scalar(select(func.count(PayrollEntry.id)).where(PayrollEntry.organization_id == org_id, PayrollEntry.run_id == run.id,
                                                                   payroll_entry_clause(scope, org_id))) or 0
    if visible == 0:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if whole and visible < total:
        raise HTTPException(status_code=403, detail={"code": "authorization_out_of_scope"})
