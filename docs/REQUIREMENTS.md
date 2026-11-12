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
