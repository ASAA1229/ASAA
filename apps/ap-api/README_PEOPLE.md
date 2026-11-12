# ASAA People API — HR, Onboarding and Payroll

The people domains are API routers and data models inside the existing ASAA API runtime. They reuse the shared SQLAlchemy database, verified JWT principal, permission dependency and audit-event table.

See docs/HR_ONBOARDING_PAYROLL_FOUNDATION_STATUS.md for implementation scope, policy boundaries, verification and production release gates.

## Authorization claims

### HR
- hr:employee:read — read organization-scoped employee profiles and employment history.
- hr:employee:write — create and edit allow-listed employee profile fields.
- hr:employee:lifecycle — perform controlled operational lifecycle transitions.
- hr:employment:write — append effective-dated employment history.
- hr:document:read / hr:document:write — read document metadata and register/archive references.
- hr:asset:read / hr:asset:write — read asset assignments and issue/return assets.
- hr:leave:read / hr:leave:request / hr:leave:review — read, submit and independently review leave requests.
- hr:exit:read / hr:exit:write / hr:exit:complete — manage exit cases and complete closure gates.

### Onboarding and offboarding
- onboarding:read — read templates, assignments and tasks.
- onboarding:template:write — create, revise, version and deactivate templates.
- onboarding:assignment:write — assign a template to an employee.
- onboarding:task:update — update task status, evidence and due date.
- onboarding:task:assign — assign or unassign a task owner subject.

### Salaries and payroll
- payroll:compensation:read / payroll:compensation:write / payroll:compensation:approve
- payroll:period:write / payroll:period:close
- payroll:run:write / payroll:run:submit / payroll:run:approve / payroll:run:close
- payroll:entry:write
- payroll:read

Sensitive salary access is separate from general HR access. Do not grant compensation/payroll claims to managers or HR users by default. Approval claims should be assigned to independently authorized reviewers. The API enforces maker-checker separation for leave, compensation and payroll-run decisions.

## Main workflow capabilities

- Employee profiles, effective-dated employment history and audited lifecycle changes.
- Employee document metadata, classification, issue/expiry dates and archive status. The API stores opaque storage references only; it does not upload or serve document bytes.
- Asset issue/return register and offboarding asset-return gate.
- Leave request submission, date-overlap prevention and independent review. Leave balances, accruals and legal entitlements are not calculated.
- Offboarding cases with optional versioned Offboarding checklist templates. Required tasks and tracked asset returns must be complete before exit closure.
- Versioned Onboarding and Offboarding templates. Assignments preserve the template version and snapshot task definitions, so later template revisions do not rewrite existing assignments.
- Task owner role, assignee subject, required/optional flag, due date, evidence reference and completion state.
- Effective-dated compensation records with independent approval and overlap prevention.
- Payroll input periods, draft runs, explicit employee inputs, arithmetic validation, run totals, review, return for correction, resubmission, approval, closure and period closure.

## Policy and integration boundaries

- No jurisdiction, legal entity, tax treatment, statutory deduction, leave entitlement, salary band, pay frequency, overtime rule, benefit policy or approval authority is assumed.
- Payroll entries are caller-supplied explicit inputs. The API checks gross minus deductions equals net; it does not calculate or certify payroll.
- No payslip generation, bank detail storage, bank file, payment initiation, payment confirmation or statutory filing is implemented.
- Document binary storage, e-signatures, identity/eligibility verification, access provisioning/revocation, device management and notifications require approved provider integrations.
- No employee document content or sensitive identity data should be placed in free-form evidence or payroll breakdown fields.
- All records are organization-scoped. All sensitive operations are permission-gated and audited.

## Migrations and tests

Apply the Alembic chain through revision 0008_onboarding_assignment_version before using the new schema. Current people-domain revisions:
- 0003_people_foundation
- 0004_onboarding_task_description
- 0005_people_workflows
- 0006_onboarding_template_version
- 0007_offboarding_checklists
- 0008_onboarding_assignment_version

Tests are in apps/ap-api/tests/test_people.py. The GitHub Actions workflow compiles source, runs the full API test suite and checks SQLite migration upgrade/downgrade/upgrade. PostgreSQL migration, identity-provider integration, security/privacy review, concurrency testing and business UAT remain separate production gates.
