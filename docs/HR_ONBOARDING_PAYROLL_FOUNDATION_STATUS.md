# HR, Onboarding and Salaries & Payroll — Foundation Status

**Repository:** ASAA1229/ASAA  
**Branch:** new  
**Scope:** Reusable API-first foundations for an early-stage organization. These capabilities are not a production-ready HR/payroll release.

## Delivery summary

| Domain | Current foundation | State |
|---|---|---|
| Employee records | Profiles, controlled edits, organization scoping, effective-dated employment history and lifecycle changes | Built |
| Employee records and evidence | Document metadata, classification, expiry dates and archive status; private binary storage is external | Partially built |
| Assets | Issue/return register and offboarding return gate | Built |
| Leave | Requests, overlap prevention and independent review; no leave entitlement/balance calculation | Partially built |
| Offboarding | Exit cases, effective-dated status history, optional offboarding checklist and outstanding-asset gate | Partially built |
| Onboarding | Versioned templates, assignment snapshots, task ownership, due dates, evidence and progress | Built |
| Compensation | Restricted effective-dated records, maker-checker approval and sequential period handling | Built |
| Payroll | Manual inputs, arithmetic validation, totals, submit/review/return/correct/approve/close and period close | Partially built |

## HR and employee lifecycle

Implemented:
- Organization-scoped employee creation, listing, detail and allow-listed profile editing.
- Employee code uniqueness within an organization.
- Effective-dated employment records with overlap prevention, previous-record closure and synchronization of current employee status/type.
- Controlled operational lifecycle changes with reason, permission separation and audit events.
- Document metadata with classification, issue/expiry dates and archive lifecycle. Binary content is not stored by this API; storage_reference must point to an approved private document service.
- Asset issue/return records; an employee exit case cannot be completed while assets remain issued.
- Leave requests with date validation, overlap prevention and independent reviewer decisions. The system does not calculate leave entitlement, accrual or balances.
- Exit cases create effective-dated Offboarding history and can snapshot an Offboarding template. Completion requires required checklist tasks to be Completed/Waived and all tracked assets to be returned.

Still gated:
- Recruitment, candidate management, interviews, offers and contract generation.
- Document upload/download, e-signatures, identity/eligibility checks, consent, retention schedules, legal holds and automated expiry notifications.
- Attendance, shifts, timesheets and time-based pay inputs.
- Leave balances, accruals, holidays and statutory leave rules.
- Performance, learning, certification, confidential employee-relations/grievance cases and appeals.
- Identity-provider access revocation, device-management integration, final settlement and handover evidence beyond configured checklist tasks.

## Onboarding and offboarding

Implemented:
- Templates are typed as Onboarding or Offboarding, versioned, editable and deactivatable.
- Assignments preserve the exact template version and task title/description snapshots.
- Active assignments are not rewritten when a template is revised.
- Tasks support owner role, explicit assignee subject, required/optional state, due date, evidence reference and status.
- Assignment progress is based on required task completion; optional-only plans do not block completion.
- Exit cases may instantiate an Offboarding template as a checklist. Required tasks and tracked asset returns are closure gates.

Still gated:
- Document collection and e-signature provider integration.
- Automated identity, eligibility, application-access and device provisioning/revocation.
- Notification delivery, reminders, escalation schedules, configurable SLA policies and calendar integrations.
- Role-specific learning/certification provider integrations.

## Salaries and payroll

Implemented:
- Restricted effective-dated compensation records with independent maker-checker approval.
- Sequential approved compensation periods close the preceding open-ended record; overlapping approved periods are rejected.
- Payroll periods and organization-scoped runs.
- Explicitly supplied payroll entries with currency, gross, deductions, net and structured input breakdown.
- Arithmetic reconciliation validation and run-level totals.
- Draft -> In Review -> Approved -> Closed workflow, with reviewer return-for-correction, controlled entry correction and resubmission.
- Maker-checker separation for compensation and payroll run approval.
- A payroll period can close only after its runs are closed.

Still gated:
- Payroll calculations, salary structures, allowances, benefits, overtime, attendance/leave inputs, tax, withholding, statutory contributions and jurisdiction-specific rules.
- Source-system ingestion, duplicate/source-reference reconciliation, exception handling and approved payroll input assembly.
- Payslip generation/publication, bank files, payment execution, payment confirmation and statutory filings.
- Reopening/adjustment workflows for closed payroll periods.

**Important:** The API stores explicit payroll inputs and validates arithmetic. It does not calculate or certify statutory or policy-specific pay. No jurisdiction, tax rule, salary frequency, leave entitlement, approval matrix or payment authority has been assumed.

## Key API routes

### HR
- POST/GET /api/v1/hr/employees
- GET /api/v1/hr/employees/{employee_id}
- PATCH /api/v1/hr/employees/{employee_id}
- POST /api/v1/hr/employees/{employee_id}/lifecycle
- POST/GET /api/v1/hr/employees/{employee_id}/employment-records
- POST/GET /api/v1/hr/employees/{employee_id}/documents
- PATCH /api/v1/hr/documents/{document_id}/status
- POST/GET /api/v1/hr/employees/{employee_id}/assets
- POST /api/v1/hr/assets/{asset_id}/return
- POST/GET /api/v1/hr/employees/{employee_id}/leave-requests
- POST /api/v1/hr/leave-requests/{request_id}/review
- POST /api/v1/hr/employees/{employee_id}/exit-cases
- GET /api/v1/hr/exit-cases
- POST /api/v1/hr/exit-cases/{case_id}/complete

### Onboarding and offboarding
- POST/GET /api/v1/onboarding/templates
- PUT /api/v1/onboarding/templates/{template_id}
- PATCH /api/v1/onboarding/templates/{template_id}/status
- POST/GET /api/v1/onboarding/assignments
- PATCH /api/v1/onboarding/tasks/{task_id}
- PATCH /api/v1/onboarding/tasks/{task_id}/assignee

### Salaries and payroll
- POST/GET /api/v1/payroll/compensation
- POST /api/v1/payroll/compensation/{record_id}/decision
- POST/GET /api/v1/payroll/periods
- POST /api/v1/payroll/periods/{period_id}/close
- POST/GET /api/v1/payroll/runs
- POST/GET /api/v1/payroll/runs/{run_id}/entries
- GET /api/v1/payroll/runs/{run_id}/summary
- POST /api/v1/payroll/runs/{run_id}/submit
- POST /api/v1/payroll/runs/{run_id}/decision
- PATCH /api/v1/payroll/entries/{entry_id}
- POST /api/v1/payroll/runs/{run_id}/close

## Authorization

All routes use the verified organization-scoped principal and separate permission claims. HR access does not imply salary access. Review/approval endpoints enforce maker-checker separation for leave, compensation and payroll runs. Assign only the specific permissions required by a user's approved responsibilities.

## Migrations and verification

People-domain migrations:
- 0003_people_foundation
- 0004_onboarding_task_description
- 0005_people_workflows
- 0006_onboarding_template_version
- 0007_offboarding_checklists
- 0008_onboarding_assignment_version

CI compiles the source, runs the complete API test suite and exercises the Alembic upgrade/downgrade/upgrade chain on SQLite. This verifies API-level behavior and migration syntax against SQLite only. It does not certify PostgreSQL production migration, identity-provider claims, binary document storage, concurrency under load, legal compliance, security/privacy review or business-policy UAT.

## Release gates

Before production use:
1. Confirm legal entity, operating jurisdictions and applicable employment/payroll requirements.
2. Approve employment, leave, document classification/retention, compensation and payroll policies.
3. Configure role/permission assignments, approvers, maker-checker rules and employee data scopes.
4. Select and integrate approved identity, document storage, notification, device/access and payroll-source providers.
5. Run PostgreSQL integration/migration tests, security/privacy review, concurrency tests, restore tests and business UAT.
6. Build the employee/admin UI and operational reporting on top of these stable API contracts.

No deployment, production data migration, identity-provider connection or external payment integration has been performed.
