# ASAA People API — HR, Onboarding and Payroll

The people domains are implemented as separate API routers and data models inside the existing ASAA API runtime. They reuse the shared SQLAlchemy database, JWT principal, permission dependency and audit-event table.

See [HR, Onboarding and Salaries & Payroll Foundation Status](../../docs/HR_ONBOARDING_PAYROLL_FOUNDATION_STATUS.md) for implemented scope, boundaries and verification status.

## Authorization claims

### HR
- `hr:employee:read`
- `hr:employee:write`
- `hr:employment:write`

### Onboarding
- `onboarding:read`
- `onboarding:template:write`
- `onboarding:assignment:write`
- `onboarding:task:update`

### Salaries & Payroll
- `payroll:compensation:read`
- `payroll:compensation:write`
- `payroll:period:write`
- `payroll:run:write`
- `payroll:entry:write`
- `payroll:read`

Salary/compensation claims are separate from general HR employee-read access. Do not grant them to managers or HR users by default; configure them explicitly according to ASAA-approved role and data-scope policy.

## Data and policy boundaries

- Employee, employment, onboarding and payroll records are organization-scoped.
- Employment history is effective-dated; changes are appended as new records rather than overwriting past assignments.
- Onboarding assignments snapshot template tasks so later template edits do not silently rewrite an employee's active checklist.
- Payroll entries are draft inputs. No jurisdiction-specific tax, statutory contribution, deduction or salary calculation is inferred.
- Payroll approval, finalization, payslips, bank files and payment execution are not part of this foundation.
- Do not put bank credentials, identity secrets or unnecessary sensitive data into free-form breakdown/evidence fields.

## Migration and tests

Run the existing Alembic migration chain, including `0003_people_foundation`, before using these endpoints. Tests are in `apps/ap-api/tests/test_people.py`; execution has not yet been verified.
