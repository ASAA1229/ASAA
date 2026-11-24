"""Data-scope predicates for people records (D3.14). An employee's unit/department is the department_id of the employment record in force today."""
from datetime import date

from sqlalchemy import or_, select

from asaa_governance.scope import AccessScope
from asaa_people.models import Employee, EmploymentRecord, PayrollEntry


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
