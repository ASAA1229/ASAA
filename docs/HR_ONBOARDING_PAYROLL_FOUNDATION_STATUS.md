# HR, Onboarding and Salaries & Payroll — Foundation Status

**Repository:** ASAA1229/ASAA  
**Branch:** new  
**Implementation status:** Built — API suite and SQLite migration-chain CI passed; PostgreSQL integration, identity-provider integration and business-policy UAT remain pending  
**Scope:** Initial domain foundation and API contracts; not a production-ready HR/payroll release.

## HR foundation

Additional hardening implemented in this round:
- Controlled employee profile patch endpoint with field allow-list, organization-scoped duplicate employee-code check and audit event.
- Explicit lifecycle transition endpoint for Preboarding, Active, On Leave, Suspended, Offboarding and Inactive operational states.
- Lifecycle transitions create effective-dated employment-history records, close the previous open-ended record and preserve the stated reason.
- Lifecycle changes use the separate `hr:employee:lifecycle` permission; profile edits use `hr:employee:write`.

Implemented:
- Organization-scoped employee profile creation, list and detail.
- Employee code uniqueness within the organization.
- Employment type and preboarding status capture.
- Effective-dated employment records for department, position, manager, work location and employment status.
- Employment history retrieval.
- Dedicated employee and employment permissions.
- Audit events for employee and employment-record creation.

Not yet implemented:
- Recruitment/candidate pipeline, offers and contract lifecycle.
- Employee document vault, consent, retention and expiry workflows.
- Attendance, leave, shifts, timesheets, performance, learning and employee relations.
- Full organization directory and department/position master-data integration.

## Onboarding foundation

Implemented:
- Reusable onboarding templates with ordered task definitions.
- Template assignment to an employee.
- Task snapshots created from the template at assignment time, including task descriptions.
- Task ownership role, required/optional flag, due date, evidence reference and status.
- Assignment progress derived from required task completion; optional-only assignments are marked complete without requiring optional tasks.
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
- `PATCH /api/v1/hr/employees/{employee_id}`
- `POST /api/v1/hr/employees/{employee_id}/lifecycle`
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

## Foundation hardening and remaining controls

- Payroll-entry input validation now rejects deductions greater than gross and rejects a net amount that does not reconcile to gross minus deductions. This is arithmetic integrity validation only; ASAA still does not calculate statutory or policy-specific payroll.
- Onboarding assignments with no required tasks are marked Completed at assignment time; optional tasks do not block completion. Task descriptions are preserved in immutable assignment snapshots.
- Added API tests for employee profile updates, lifecycle history and payroll arithmetic rejection.
- Remaining foundation work includes template lifecycle/versioning, richer assignment ownership/due-date controls, employee document/consent/retention handling, approval workflow integration, payroll input-source reconciliation and configurable calculation policies.

## Verification

Seven people-domain API tests are included in the full suite. GitHub Actions completed successfully: **26 tests passed** (one Starlette/httpx deprecation warning), source compilation passed, and the Alembic chain successfully upgraded through `0004_onboarding_task_description`, downgraded one revision and upgraded again using SQLite.

Alembic revision `0003_people_foundation` follows `0002_ar_foundation`; `0004_onboarding_task_description` adds the task-description snapshot field. The SQLite migration chain is verified in CI. PostgreSQL behavior, production database migration, identity-provider claims, concurrency under load, privacy/security review and business UAT remain unverified.

CI Passed means the current automated checks and SQLite migration-chain checks succeeded. It does not certify PostgreSQL production migration, identity-provider integration, security/privacy review, legal compliance or business-policy acceptance.
