# ASAA Consolidated Requirements

**Status:** Consolidated product baseline for owner validation  
**Scope:** Internal ASAA Enterprise Operating Platform  
**Important:** This document describes target capabilities. It does not assert that all capabilities are implemented, staffed, legally applicable or approved.

## 1. Product outcome

Provide one secure, configurable operating environment through which ASAA can manage its organization and connect people, authority, policies, work, projects, products, services, customers, commercial commitments, finance, assets, operations, compliance and organizational intelligence.

The platform must suit an early-stage organization where a small number of people may hold multiple roles. It must support future growth without forcing departments, legal entities, policies, technologies or processes to exist before they are confirmed.

## 2. Priority and delivery vocabulary

- **P0 — Foundation:** required to safely establish dependent capabilities.
- **P1 — Core operating releases:** important for coherent day-to-day operations.
- **P2 — Expansion:** capabilities to introduce after foundations and workflows are validated.

Implementation status:
- **Not Started:** no implementation evidence.
- **Built:** implementation exists; verification not yet established.
- **Built Not Tested:** source/tests exist but current successful execution evidence is absent or incomplete.
- **Passed:** identified automated/manual verification passed in a stated environment.
- **Blocked:** progress depends on an external decision, provider, policy or prerequisite.
- **Deferred:** intentionally postponed.

Do not use a single percentage to imply completion where measurable scope and evidence are absent. Every status should identify its evidence, revision, environment and verification date.

## 3. Product-wide functional requirements

### A. Organization, governance and administration — P0/P1
- Configure organization profile, legal entities, business units, divisions, departments, teams and locations with effective dates and history.
- Keep the department catalogue configurable; activate only capabilities the organization actually needs.
- Manage people and organizational membership, including employees and authorized external collaborators.
- Distinguish job titles, system roles, reporting relationships and approval authority.
- Configure role/permission templates and data scopes at organization, unit, department, project, customer and record levels.
- Maintain delegations, authority limits, approval matrices, policy exceptions, decision registers and emergency access with expiry/review.
- Maintain versioned policies, procedures, owners, effective dates, approvals and acknowledgements where required.
- Track risks, compliance obligations, internal controls, incidents and corrective actions.
- Support the company's pre-incorporation-to-established lifecycle without treating planned legal entities or registrations as active until confirmed.

Acceptance: structure and authority are configurable and auditable; historical relationships are preserved; privileged and sensitive access is separately granted; no legal status or authority is inferred.

### B. Shared platform foundations — P0
- Organization-scoped identity, authentication, authorization and delegated administration.
- Configurable reference data, statuses, currencies, locations and metadata.
- Workflow/state-transition and approval engine supporting submit, review, approve, reject, return for correction, delegate, cancel and escalate where configured.
- Maker-checker and separation-of-duties controls.
- Append-only application audit history with actor, timestamp, action, target, scope, outcome and correlation reference.
- Document/attachment metadata, classification, versioning, access control and retention integration.
- Notification and communication services with delivery status and preferences.
- Integration registry with scoped credentials, health, sync history, retry and reconciliation.
- Search, reporting and exports that enforce the same access controls as source records.
- Configurable forms and field-level sensitivity.

Acceptance: shared services are reusable without coupling domain ownership; authorization is checked server-side; audit events are traceable; integration failure and stale data are visible.

### C. People, HR and workforce — P0/P1/P2
- Employee and collaborator profiles, employment history, organization placement and lifecycle.
- Recruitment: vacancies, candidate records, interviews, evaluation and offer approvals.
- Onboarding: versioned checklists, tasks, documents, equipment, access requests, owners and due dates.
- Employment changes: transfer, promotion, manager/team/contract changes and effective dates.
- Offboarding: handover, checklist, asset return, final-settlement inputs, document retention and access revocation.
- Restricted employee document records, private binary storage, evidence, expiry reminders, acknowledgement and retention/legal hold.
- Asset issue, return, maintenance and ownership.
- Attendance, shifts, rosters, holidays, breaks, overtime and remote/hybrid/field arrangements.
- Leave requests, configurable types, balances, accrual, holiday calendars, eligibility and approvals.
- Work logs, timesheets, project allocation, manager review and approved time inputs.
- Compensation history, salary structures, allowances, benefits, deductions, payroll inputs, payslips and payroll reconciliation.
- Performance goals/reviews, feedback, development plans, training, learning and certifications.
- Confidential employee relations, grievances, investigations and appeals with restricted access.

Acceptance: employee history and sensitive changes are auditable; policies are effective-dated and configurable; sensitive HR/payroll data is not exposed by general manager/HR permissions; payroll and legal calculations are not enabled without confirmed rules and independent review.

### D. Projects, products, engineering and technology — P0/P1/P2
- Portfolio, project/program registry, ownership, scope, milestones, budgets, dependencies and risks.
- Requirements, acceptance criteria, specifications, roadmaps, change requests and decision history.
- Product discovery, lifecycle, versions, features, pricing, packaging and retirement.
- Repository and branch metadata, code review, engineering tasks and release evidence.
- QA strategy, test plans, test cases, defects, test runs and quality gates.
- Environments, configuration, CI/CD, artifacts, deployments, rollback and support.
- Architecture/component catalogues, APIs, data stores, events, integrations and technical dependencies.
- Project status based on traceable implementation, test, security and operational evidence.

Acceptance: each project retains independent scope, stack, repository and delivery workflow; organization views aggregate without rewriting project records; repository intelligence is read-only unless a separate write feature is approved.

### E. Services, delivery and operations — P1/P2
- Service catalogue, service requests, work orders, delivery commitments and operational ownership.
- Client onboarding, statements of work, scheduling, queues, SLAs, escalation and support.
- Work allocation, operational checklists, SOPs, quality controls and incident management.
- Supplier/vendor lifecycle, procurement requests, quotations, purchase orders, receipts and supplier performance.
- Inventory, stock, equipment, asset maintenance, disposal, facilities, travel and logistics.
- Capacity, service performance and operational reporting.

Acceptance: operational workflows have owners, states, evidence, permissions and escalation rules; procurement and supplier controls integrate with finance without duplicate sources of truth.

### F. Sales, customers and marketing — P1/P2
- Leads, prospects, customer accounts, contacts and CRM pipeline.
- Proposals, quotations, estimates, contracts, renewals, sales orders and subscriptions.
- Customer onboarding, communications, service entitlements, support, feedback and satisfaction.
- Marketing plans, campaigns, channels, content, brand assets and partnerships.
- Revenue pipeline, forecasts and customer/project profitability.

Acceptance: commercial commitments link to authoritative customer, contract, project and finance records; access to customer data is scoped.

### G. Finance, accounting and commercial control — P0/P1/P2
- Budgets, forecasts, cost centres, project budgets and approvals.
- Estimates, quotations, invoices, credit/debit notes, receipts and payment tracking.
- Accounts payable and receivable, supplier/customer masters, expenses, reimbursements and advances.
- Cash flow, revenue, cost, margin, profitability and financial reporting.
- Accounting dimensions, chart of accounts, journals, reconciliation and accounting integrations.
- Payroll accounting and approved finance exports.
- Tax, statutory reporting, invoice numbering, e-invoicing and jurisdiction-specific controls only after legal jurisdiction and applicable rules are confirmed.

Acceptance: monetary calculations use decimal-safe arithmetic and explicit currency; financial events reconcile; recording a receipt is not represented as initiating or verifying a bank transfer; payment execution is a separately authorized integration.

### H. Legal, compliance, security and privacy — P0/P1
- Contract repository, obligations, renewal dates and approval history.
- Policy and regulatory registers, evidence, compliance calendars and corrective actions.
- Consent, privacy requests, retention, legal holds, export and lawful deletion.
- Identity lifecycle, MFA/SSO, access reviews and privileged access.
- Security incidents, risk assessments, vulnerability remediation and audit findings.
- Data classification, encryption, backup, recovery and breach response.
- Jurisdiction-specific obligations only when applicability is confirmed.

### I. Knowledge, communication and collaboration — P1/P2
- Knowledge base, controlled documents, version history and search.
- Announcements, internal communication, team spaces and discussions.
- Calendars, meetings, minutes, decisions, action items and follow-ups.
- Forms, requests, approvals, notifications, reminders and controlled external sharing.

### J. Analytics, intelligence and automation — P1/P2
- Executive and department dashboards with configurable KPIs and targets.
- Operational, workforce, delivery, finance, sales and product analytics.
- Cross-domain reporting with source lineage, permissions and freshness indicators.
- Forecasting and scenarios with assumptions and uncertainty disclosed.
- AI-assisted search, summarization and recommendations grounded in approved evidence.
- Automation catalogue with scoped triggers/actions, approvals, dry-run, idempotency, logs, stop controls and recovery/compensation.

Acceptance: no AI inference is presented as confirmed fact; no recommendation changes business data; write automation is disabled until explicitly authorized and approved.

## 4. Project and repository preservation requirements

- Projects have independent identifiers, owners, scope, requirements, repositories and approval authority.
- One project may have multiple repositories; heterogeneous stacks and directory structures are supported.
- Organization default branch names are `main`, `dev`, `new`, `fix`, `test`; additional branches are allowed.
- Branch protections, merge flow, release process, directory structures and project specifications remain project-specific.
- The initial project-intelligence capability is read-only: discover metadata, branches, revisions, directory trees and selected files; never write, execute scripts, create branches or trigger pipelines.
- Every finding retains project, repository, branch, revision, path, timestamp, classification and reviewer state.
- Requirements are separate from findings; cross-project dependencies are explicit references, not project/repository mergers.
- Missing branch names are reported as gaps for owner action, not automatically created.

## 5. Evidence and requirement lifecycle

Evidence classes: stakeholder-confirmed, documented, code-observed, test-verified, operationally verified, inferred, assumed and unknown.

Suggested requirement states: Proposed, Under Review, Approved, In Progress, Implemented, Test Pending, Verified, Blocked, Deferred and Rejected.

Verification rules:
- Code presence is not proof of completion.
- Test-verified claims require an identified test run, revision, environment and result.
- Operationally verified claims require the target environment and recorded verification.
- Unknown, stale and unavailable evidence remains visible.
- Decisions and status changes retain actor, time and rationale.

## 6. Current implementation baseline (branch `new`)

### Finance API
**Supplier/AP foundation — Built:** organization-scoped supplier registration/list/detail, duplicate checks, controlled status transitions, optimistic version checks, permission gates and audit events. Purchase requests, quotations, purchase orders, receipts, supplier invoices, matching, payment, bank and tax workflows are not included.

**AR foundation — Built:** customer registration/lookup, draft invoice creation/editing, decimal line/subtotal/tax/total calculations, permission-gated invoice issue, receipt recording and partial/unapplied allocation. No tax rates, FX, e-invoicing, payment initiation, bank settlement verification, refunds, credit notes, disputes or bank reconciliation are assumed.

### People API
**HR — Built:** organization-scoped employee profiles, allow-listed edits, effective-dated employment records, lifecycle transitions with reason/permission/audit, document metadata, asset issue/return, leave requests with overlap checks and independent review, exit cases and closure gates.

**Onboarding/offboarding — Built:** typed/versioned templates, assignment snapshots, required/optional tasks, assignee/owner, due dates, evidence references, task updates and offboarding closure checks.

**Compensation/payroll — Built:** restricted effective-dated compensation with maker-checker approval; periods/runs; explicit caller-supplied employee payroll inputs; arithmetic validation; run summary; review, return for correction, resubmission, approval and closure. It does not calculate statutory or policy-specific payroll or initiate payments.

**Verification evidence:** latest recorded CI on this branch reported 31 tests passed, source compilation passed, and Alembic upgrade/downgrade/upgrade passed on SQLite. This does not establish PostgreSQL, real identity provider, production security, concurrency, backup/recovery or business UAT. Re-run CI against the current revision before relying on it.

## 7. Known gaps and release gates

- User-facing employee, manager, finance and admin UI/portal.
- Approved identity provider, signing-key distribution, MFA/SSO and role mapping.
- PostgreSQL migration and runtime integration tests.
- Security/privacy review, concurrency/load testing and access-control testing.
- Production document storage, e-signatures, retention/legal hold and expiry notifications.
- Notifications, reminders, escalation and calendar integrations.
- Recruitment, attendance, shifts, timesheets, leave balances, performance, learning and employee relations.
- Payroll source ingestion, approved salary rules, tax/statutory calculations, payslips and payment integrations.
- Full AP procurement/invoice/payment lifecycle; AR reconciliation, refunds, credit notes, disputes, bank reconciliation and reporting.
- CRM, contracts, projects/products, delivery, inventory, procurement and broader enterprise modules.
- Backup/restore validation, operational monitoring, incident response and deployment automation.
- Owner-approved legal entity, jurisdiction, employment, finance, retention, approval and delegation policies.

## 8. Discovery and owner decisions

Before enabling dependent production workflows, confirm: legal entity and locations; active departments and reporting; people and role assignments; approval matrix and authority limits; data classification and retention; payroll/leave/finance rules; identity/document/notification providers; hosting and recovery objectives; integrations; reporting KPIs; and support ownership.

## 9. Acceptance approach

Each epic is decomposed into uniquely identified requirements/stories with priority, owner, rationale, acceptance criteria, dependencies, status, evidence and decision history. A release is accepted only when the applicable criteria have been tested in the target environment, security and operational gates are satisfied, and business owners approve the workflow. Deferred capabilities remain visible in the backlog rather than being silently removed.


## 10. Current API reference

The following route groups describe the implemented API surface on the current branch. The live OpenAPI schema for the checked-out revision remains authoritative.

### Supplier / Accounts Payable
- Supplier operations: `/api/v1/suppliers` (create, list, detail, controlled update and status transition).
- Permissions: `supplier:read`, `supplier:write`, `supplier:status`, `supplier:verify`; shared audit access: `audit:read`.
- New suppliers begin in Draft; activation requires verification permission. Supplier records are organization-scoped and have no delete endpoint.

### Accounts Receivable
- Customers: `POST/GET /api/v1/ar/customers`, `GET /api/v1/ar/customers/{customer_id}`.
- Invoices: `POST/GET /api/v1/ar/invoices`, `PUT /api/v1/ar/invoices/{invoice_id}` (Draft only), `GET /api/v1/ar/invoices/{invoice_id}`, `POST /api/v1/ar/invoices/{invoice_id}/issue`.
- Receipts: `POST/GET /api/v1/ar/receipts`, `POST /api/v1/ar/receipts/{receipt_id}/allocations`.
- Permissions: `ar:customer:read`, `ar:customer:write`, `ar:invoice:read`, `ar:invoice:write`, `ar:invoice:issue`, `ar:receipt:read`, `ar:receipt:write`, `ar:receipt:allocate`, and `audit:read`.

### HR and employee lifecycle
- Employees: `POST/GET /api/v1/hr/employees`, `GET/PATCH /api/v1/hr/employees/{employee_id}`.
- Lifecycle and employment: `POST /api/v1/hr/employees/{employee_id}/lifecycle`, `POST/GET /api/v1/hr/employees/{employee_id}/employment-records`.
- Documents: `POST/GET /api/v1/hr/employees/{employee_id}/documents`, `PATCH /api/v1/hr/documents/{document_id}/status`.
- Assets: `POST/GET /api/v1/hr/employees/{employee_id}/assets`, `POST /api/v1/hr/assets/{asset_id}/return`.
- Leave: `POST/GET /api/v1/hr/employees/{employee_id}/leave-requests`, `POST /api/v1/hr/leave-requests/{request_id}/review`.
- Exit: `POST/GET /api/v1/hr/employees/{employee_id}/exit-cases`, `GET /api/v1/hr/exit-cases`, `POST /api/v1/hr/exit-cases/{case_id}/complete`.
- Permissions: `hr:employee:read`, `hr:employee:write`, `hr:employee:lifecycle`, `hr:employment:write`, `hr:document:read`, `hr:document:write`, `hr:asset:read`, `hr:asset:write`, `hr:leave:read`, `hr:leave:request`, `hr:leave:review`, `hr:exit:read`, `hr:exit:write`, `hr:exit:complete`.

### Onboarding and offboarding
- Templates: `POST/GET /api/v1/onboarding/templates`, `PUT /api/v1/onboarding/templates/{template_id}`, `PATCH /api/v1/onboarding/templates/{template_id}/status`.
- Assignments/tasks: `POST/GET /api/v1/onboarding/assignments`, `PATCH /api/v1/onboarding/tasks/{task_id}`, `PATCH /api/v1/onboarding/tasks/{task_id}/assignee`.
- Permissions: `onboarding:read`, `onboarding:template:write`, `onboarding:assignment:write`, `onboarding:task:update`, `onboarding:task:assign`.

### Compensation and payroll
- Compensation: `POST/GET /api/v1/payroll/compensation`, `POST /api/v1/payroll/compensation/{record_id}/decision`.
- Periods/runs: `POST/GET /api/v1/payroll/periods`, `POST /api/v1/payroll/periods/{period_id}/close`, `POST/GET /api/v1/payroll/runs`, `POST/GET /api/v1/payroll/runs/{run_id}/entries`, `GET /api/v1/payroll/runs/{run_id}/summary`, `POST /api/v1/payroll/runs/{run_id}/submit`, `POST /api/v1/payroll/runs/{run_id}/decision`, `PATCH /api/v1/payroll/entries/{entry_id}`, `POST /api/v1/payroll/runs/{run_id}/close`.
- Permissions: `payroll:compensation:read`, `payroll:compensation:write`, `payroll:compensation:approve`, `payroll:period:write`, `payroll:period:close`, `payroll:run:write`, `payroll:run:submit`, `payroll:run:approve`, `payroll:run:close`, `payroll:entry:write`, `payroll:read`.
- Payroll permissions are separate from general HR permissions. Assign only the minimum approved claims; approval permissions belong to independently authorized reviewers.

## 11. Initial project-intelligence proof of concept

The initial project/repository intelligence slice is deliberately read-only. Its validation workflow is:
1. Register a workspace and a real project with purpose, owner and scope.
2. Capture stakeholder requests and their source.
3. Connect an authorized repository using read-only access.
4. Discover provider metadata, default branch, branches, revisions and directory tree without executing files.
5. Select relevant documentation/source paths and record exact evidence references.
6. Capture requirements, priorities, owners and measurable acceptance criteria.
7. Link findings to requirements without automatically marking them complete.
8. Record dependencies, risks, assumptions, decisions and unknowns.
9. Generate project summaries and evidence-based gap reports.
10. Obtain project-owner/technical-reviewer validation.

POC acceptance requires project/repository registration; read-only branch and directory discovery; branch-name baseline comparison; exact revision/path provenance; requirement and evidence separation; visible unknown/inferred states; reviewer decisions; traceable reports; audit history; and proof that no repository mutation or script execution occurred.

The project-intelligence capability is not yet represented by a running application in this repository. Its workflow remains a target requirement, not an implemented feature.

## 12. Additional enterprise gap-closure requirements

The consolidated backlog must retain the following cross-cutting capabilities as explicit requirements rather than silently dropping them:
- Company establishment lifecycle, legal-entity activation gates and jurisdiction-aware configuration.
- Delegations, authority expiry, policy exceptions, emergency access and decision registers.
- Configurable master data, data ownership, source lineage and effective-dated policy versions.
- Cross-domain identity and record links without duplicate sources of truth.
- Integration health, incremental synchronization, idempotent retry, reconciliation and stale-data detection.
- Data classification, retention/legal hold, lawful deletion, export and privacy request workflows.
- Backup/restore, disaster recovery, incident response and operational readiness.
- Notifications, reminders, escalation, search, controlled export and executive reporting.
- Shared engineering services and portfolio visibility without forcing identical project stacks or workflows.
- Guarded AI recommendations and automation with evidence, scoped permissions, human approval, dry-run, audit and recovery.

These remain planned requirements until implementation and acceptance evidence exists.


## 13. P0 gap closure implementation record

### ASAA-GAP-024 — Govern master data and record ownership

**Status:** Passed — GitHub Actions run [43220389874](https://github.com/ASAA1229/ASAA/actions/runs/43220389874), commit `1340bcd9c996d88a3108a8d7f88107738eaf29b3`.

The API foundation introduces an organization-scoped master-data registry:
- Domain registration records a domain code, authoritative-source label, accountable owner subject and steward subject.
- Domain metadata can be updated with optimistic version checks.
- Record references identify the source system and source record without copying the underlying employee, supplier, customer, product or asset payload.
- A trusted caller may provide a keyed match fingerprint. Matching active references are returned as duplicate candidates and the new reference is placed in `Duplicate Review`; no automatic merge occurs.
- A steward with explicit supersession permission may link a duplicate reference to an active canonical reference, preserving the old reference and reason.
- Organization scoping, separate domain/record permissions and audit events are enforced.

API routes:
- `POST/GET /api/v1/master-data/domains`
- `PATCH /api/v1/master-data/domains/{domain_id}`
- `POST/GET /api/v1/master-data/domains/{domain_id}/records`
- `POST /api/v1/master-data/records/{record_id}/supersede`

Permissions:
- `masterdata:domain:read`
- `masterdata:domain:write`
- `masterdata:record:read`
- `masterdata:record:write`
- `masterdata:record:supersede`

Security and scope limits:
- The registry is metadata/provenance governance, not a replacement source of record for domain entities.
- Fingerprints must be keyed HMAC or equivalent pseudonymous values generated by trusted code. Never submit raw personal identifiers, email addresses, phone numbers or other sensitive values.
- Duplicate matches are candidates for human review, not proof that records represent the same entity.
- Supersession is non-destructive; there is no automatic merge or delete.
- The registry does not yet enforce domain ownership on writes to the underlying HR/AP/AR tables. That integration is a subsequent gap-closure step.
- No production identity provider, UI or PostgreSQL verification is implied.

Automated tests added cover domain creation/list/audit, duplicate domain rejection, optimistic version conflict, duplicate-candidate flagging, source/record uniqueness, non-destructive supersession, organization isolation and separate permissions. The exact commit passed source compilation, the full 37-test API suite and SQLite Alembic upgrade/downgrade/upgrade checks. PostgreSQL runtime validation and production acceptance remain open.


## 14. P0 gap closure implementation record

### ASAA-GAP-002 — Decision, Delegation and Authority Register

**Status:** Built — implementation and automated validation pending CI at this revision.

The governance API adds two organization-scoped registers:

**Authority delegations**
- Records delegator and delegate subjects, scope code, action code, effective start/end, reason and optional evidence reference.
- New requests begin in `Pending Approval`; a separate authorized reviewer must approve or reject.
- The creator, delegator and delegate cannot approve or reject the same request.
- Approval is distinct from actual effectiveness. The API reports `effective_now` only when status is Approved and the current time is within the explicit effective window.
- Approved delegations can be revoked with a reason. Rejection and revocation are retained as status changes with reviewer and timestamp.
- Stale transition requests are rejected using expected record versions.

**Governance decisions**
- Records decision type, title, scope reference, rationale, designated decision-maker subject, optional effective date and evidence reference.
- New entries begin as `Proposed`; only the designated decision-maker can approve or reject, and that person cannot be the proposal creator.
- Rejection requires a reason. The proposal, reviewer, timestamp, result and reason remain available in the register.
- Decisions and delegations are organization-scoped and audited.

API routes:
- `POST/GET /api/v1/governance/delegations`
- `POST /api/v1/governance/delegations/{id}/approve`
- `POST /api/v1/governance/delegations/{id}/reject`
- `POST /api/v1/governance/delegations/{id}/revoke`
- `POST/GET /api/v1/governance/decisions`
- `POST /api/v1/governance/decisions/{id}/approve`
- `POST /api/v1/governance/decisions/{id}/reject`

Permissions:
- `governance:delegation:read`, `governance:delegation:create`, `governance:delegation:approve`, `governance:delegation:reject`, `governance:delegation:revoke`.
- `governance:decision:read`, `governance:decision:create`, `governance:decision:approve`, `governance:decision:reject`.

**Important boundary:** This register is an auditable record of authority and decisions. It does not grant, modify or inject permissions into JWT claims or the existing `require_permission` authorization path. A recorded delegation is not proof that an identity provider, employment relationship, contract or external policy authorizes the underlying action. No founder/CEO hierarchy, legal entity, department, monetary threshold, jurisdictional rule or approval matrix is assumed. These require explicit owner-approved configuration and later integration work.
