# HR, Onboarding and Salaries & Payroll — Foundation Status

**Repository:** ASAA1229/ASAA  
**Branch:** new  
**Implementation status:** Built Not Tested  
**Scope:** Initial domain foundation and API contracts; not a production-ready HR/payroll release.

## HR foundation

Implemented:
- Organization-scoped employee profile creation, list and detail.
- Employee code uniqueness within the organization.
- Employment type and preboarding status capture.
- Effective-dated employment records for department, position, manager, work location and employment status.
- Employment history retrieval.
- Dedicated employee and employment permissions.
- Audit events for employee and employment-record creation.

Not yet implemented:
- Employee profile editing and controlled lifecycle transitions.
- Recruitment/candidate pipeline, offers and contract lifecycle.
- Employee document vault, consent, retention and expiry workflows.
- Attendance, leave, shifts, timesheets, performance, learning and employee relations.
- Full organization directory and department/position master-data integration.

## Onboarding foundation

Implemented:
- Reusable onboarding templates with ordered task definitions.
- Template assignment to an employee.
- Task snapshots created from the template at assignment time.
- Task ownership role, required/optional flag, due date, evidence reference and status.
- Assignment progress derived from required task completion.
- Audit events for template creation, assignment and task updates.

Not yet implemented:
- Document collection, e-signatures, identity/eligibility checks and policy acknowledgements.
- Asset issue/return workflows and IT account provisioning integrations.
- Configurable approval gates, reminders, escalations and SLA dashboards.
- Role-specific training/certification integrations and offboarding.

## Salaries & Payroll foundation

Implemented:
- Restricted, effective-dated compensation records.
- Payroll periods and organization-scoped payroll runs.
- Draft employee payroll entries with currency, gross, deduction and net amount fields plus structured breakdown.
- Payroll entries accepted only into Draft runs.
- Separate compensation read/write, payroll read, period, run and entry permissions.
- Audit events for compensation, period, run and entry creation.

Important boundaries:
- No salary bands, pay frequency rules, allowances, benefits, tax rates, statutory contributions, withholding, overtime, leave adjustments or jurisdiction-specific rules are assumed.
- Payroll amounts are stored as explicitly supplied inputs; this foundation does not calculate or certify gross/net pay.
- No bank account details, bank file generation, payment initiation, payslip publication or payment confirmation.
- No approval/finalization/locking workflow yet. Payroll remains Draft and must not be treated as payable or approved.

## API routes

### HR
- `POST/GET /api/v1/hr/employees`
- `GET /api/v1/hr/employees/{employee_id}`
- `POST/GET /api/v1/hr/employees/{employee_id}/employment-records`

### Onboarding
- `POST/GET /api/v1/onboarding/templates`
- `POST/GET /api/v1/onboarding/assignments`
- `PATCH /api/v1/onboarding/tasks/{task_id}`

### Salaries & Payroll
- `POST/GET /api/v1/payroll/compensation`
- `POST/GET /api/v1/payroll/periods`
- `POST/GET /api/v1/payroll/runs`
- `POST/GET /api/v1/payroll/runs/{run_id}/entries`

## Verification

Four automated tests have been added for HR employee/employment history, onboarding template/assignment/task completion, payroll foundation creation and compensation permission separation. They have **not been executed** in this environment.

Alembic revision `0003_people_foundation` follows `0002_ar_foundation`. Migration execution, PostgreSQL behavior, identity-provider claims, concurrency, privacy/security review and business UAT remain unverified.

Do not classify any capability as Passed until tests and migrations run successfully and ASAA-approved HR/payroll policies and acceptance criteria are available.
