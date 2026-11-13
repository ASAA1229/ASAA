# ASAA User Stories and Acceptance Backlog

**Product:** Internal ASAA Enterprise Operating Platform  
**Baseline branch:** `new`  
**Backlog status:** Refined from the current repository implementation and documented operational evidence  
**Rule:** Built code is not automatically Verified. Provider, policy, jurisdiction and infrastructure decisions remain explicit dependencies.

## Status vocabulary

Use the canonical statuses from [Project Status](PROJECT_STATUS.md): PLANNED, NOT STARTED, IN DEVELOPMENT, IMPLEMENTED, NEEDS TESTING, TEST FAILED, TEST PASSED, CI VERIFIED, DEVICE VERIFIED, OWNER ACCEPTANCE PENDING and ACCEPTED.

Story-level labels are normalized below where practical. The project-wide gap register and maturity score in Project Status are authoritative. A source file or older successful workflow does not prove that the current branch/revision is production accepted.

## P0 — Production foundation and governance

### ASAA-P0-01 — Operate PostgreSQL safely
**Status:** CI VERIFIED — CI passed; production validation blocked by environment provisioning.

As a platform operator, I want a production PostgreSQL deployment with verified transport security, least-privilege roles, migration controls and capacity limits so that organizational records are stored safely.

Acceptance criteria:
- PostgreSQL 16+ is provisioned in an approved environment with certificate-verified TLS.
- Migration identity is separate from the runtime identity.
- Runtime identity cannot own application schema/tables, create roles/databases, bypass RLS or alter schema.
- Production preflight passes against the actual target; secrets and database URLs are redacted.
- Connection pool limits, timeouts, capacity and load behaviour are measured.
- Migration rehearsal, backup and recovery evidence is attached to the release.

### ASAA-P0-02 — Recover the platform
**Status:** NOT STARTED — — RPO, RTO, retention and hosting decisions required.

As an operations owner, I want encrypted backups, point-in-time recovery and rehearsed restore procedures so that service and data can be recovered after failure.

Acceptance criteria:
- Approved RPO, RTO, retention and residency requirements are recorded.
- Automated backups and backup-failure alerts are enabled.
- Restore is demonstrated in an isolated environment.
- Database and document/object metadata consistency is checked.
- Recovery steps, owners, measured recovery time and residual risks are recorded.

### ASAA-P0-03 — Authenticate with real SSO and MFA
**Status:** IMPLEMENTED — OIDC/RS256/JWKS foundations; provider integration pending.

As an employee, I want to sign in through the approved identity provider with enforced MFA so that I use one managed identity securely.

Acceptance criteria:
- Provider, tenant, issuer, API audience, public SPA client and exact redirect URIs are approved.
- Authorization Code + PKCE (S256), state validation, issuer/audience/signature/expiry and signing-key rotation are tested.
- MFA assurance is enforced by provider policy and validated using documented claims.
- Logout, refresh/revocation, account disablement and recovery paths are tested.
- No client secret or long-lived sensitive token is shipped or persisted in browser storage.

### ASAA-P0-04 — Provision and revoke identities
**Status:** NOT STARTED — — provider selection and authoritative identity mapping required.

As an authorized administrator, I want employee lifecycle and approved access assignments synchronized with the identity provider so that access is granted and removed at the correct time.

Acceptance criteria:
- Joiner, mover and leaver events map to provider account lifecycle operations.
- Role/scope assignments are derived only from approved, effective-dated records.
- Expired and revoked assignments remove effective access within an approved service target.
- Reconciliation identifies drift between ASAA and provider state.
- Failed provisioning/revocation is visible, retried safely and escalated.
- Emergency access is time-limited, justified and independently reviewed.

### ASAA-P0-05 — Enforce governance and authority
**Status:** IMPLEMENTED — register/workflows exist; enforcement integration pending.

As an organization owner, I want organizational units, decision authority, delegations and role assignments validated against authoritative people and scope records so that approval rights cannot be inferred from titles or stale references.

Acceptance criteria:
- Organization units and master-data references are validated and effective-dated.
- Delegations identify permitted actions, scope, limits, start/end and independent reviewer.
- Self-approval and invalid scope/subject references are rejected.
- Policy evaluation honours effective dates, expiry and revocation.
- Every decision and change is auditable.
- Register records do not grant API/provider access until the enforcement adapter is active.

### ASAA-P0-06 — Prove security and audit controls
**Status:** NEEDS TESTING — baseline controls exist; production assurance pending.

As a security owner, I want authorization, privacy, audit and incident controls tested so that sensitive employee and financial data is protected.

Acceptance criteria:
- Positive and negative permission tests cover every sensitive read/write/export/approval path.
- Cross-organization and horizontal/vertical privilege escalation tests pass.
- Audit records include actor, organization, target, action, timestamp, outcome and correlation ID.
- Audit failure is not silently ignored for protected decisions.
- Threat model, data classification, privacy review, dependency/security testing and incident exercise are approved.
- Production logs and errors do not expose tokens, secrets or restricted personal/financial data.

### ASAA-P0-07 — Operate and observe releases
**Status:** NOT STARTED — — hosting and monitoring provider decisions required.

As an operator, I want observable services and controlled releases so that failures are detected and changes can be recovered safely.

Acceptance criteria:
- Structured logs, metrics, traces and alert routing are configured.
- Alerts have severity, owner, runbook and escalation.
- Production migrations run through a controlled job with a migration-only identity.
- Releases identify commit, artifact, migration revision and approvals.
- Smoke tests and rollback/forward-recovery procedures are exercised.

## P1 — Finance, payroll and workforce

### ASAA-P1-01 — Prevent overlapping payroll periods
**Status:** CI VERIFIED — API and PostgreSQL integration CI passed on the latest payroll period test commit.

As a payroll administrator, I want payroll periods to have unique organization-scoped codes and non-overlapping date ranges so that employees cannot be included in duplicate or conflicting periods.

Acceptance criteria:
- Start date cannot follow end date.
- A period code cannot be reused within an organization; API returns a controlled conflict.
- Any date intersection with an existing period in the same organization is rejected with a stable conflict code.
- Adjacent non-overlapping periods are accepted.
- Another organization may use the same code/date range.
- Automated tests cover duplicate, overlap, adjacency and organization isolation.

### ASAA-P1-02 — Maintain a valid compensation timeline
**Status:** CI VERIFIED — effective-date overlap enforcement, safe supersession, independent decision API and PostgreSQL integration passed on commit `f3e6d46`.

As a restricted payroll operator, I want effective-dated compensation records to be consistent and independently approved so that historical and future compensation cannot conflict.

Acceptance criteria:
- Effective intervals for an employee cannot conflict.
- Approved records cannot be silently overwritten; changes are new proposals.
- Pending and approved effective intervals cannot overlap for the same employee; adjacent periods are allowed.
- Rejected proposals remain in history but do not block a replacement proposal.
- Independent approval/rejection records reviewer, timestamp and note; maker self-approval and repeated decisions are rejected.
- Corrections and supersession preserve original values and reasons.
- Currency, pay basis, frequency and effective dates are validated.
- Compensation read/write/approve permissions remain separate from general HR access.
- Maker-checker and audit tests pass.

### ASAA-P1-03 — Reconcile payroll inputs and outputs
**Status:** IN DEVELOPMENT — duplicate employee entries are now rejected per run; remaining source lineage and exception controls pending.

As a payroll reviewer, I want payroll inputs, gross, deductions and net amounts reconciled before approval so that errors are caught without inventing statutory calculations.

Acceptance criteria:
- Inputs identify their authoritative source and period.
- Duplicate employee entries within one payroll run and currency mismatches are rejected with controlled conflicts.
- Payroll run entry creation is serialized per run on databases supporting row-level locks.
- Gross less deductions equals net using decimal-safe arithmetic.
- Changes after submission require return/resubmission and independent review.
- Approved rules are versioned and independently validated before any statutory calculation is enabled.
- Payment execution is a separate authorized integration.

### ASAA-P1-04 — Manage leave under approved policy
**Status:** IMPLEMENTED — request/review; policy engine Not Started / Blocked.

As an employee, I want to request leave under published eligibility and balance rules so that I can understand available entitlement before submitting.

Acceptance criteria:
- Leave categories, holidays, working days, accrual and carry-forward are effective-dated and owner-approved.
- Balance calculations show source policy and calculation breakdown.
- Overlaps, insufficient balance and ineligible dates are rejected with actionable explanations.
- Manager/HR review, delegation, cancellation and correction are auditable.
- No balance or entitlement is fabricated before policy approval.

### ASAA-P1-05 — Complete employee lifecycle tasks
**Status:** IMPLEMENTED — checklist foundations; automation pending.

As an HR/IT manager, I want onboarding and offboarding tasks assigned, due-dated and escalated so that access, equipment, handover and employee records are handled consistently.

Acceptance criteria:
- Templates are versioned and assignments retain a snapshot.
- Tasks have accountable owners, due dates, state, evidence and audit history.
- Required incomplete tasks block closure.
- Offboarding triggers approved identity/device revocation tasks and confirms completion from connected systems.
- Reminders, escalation and failed-action handling are visible.

### ASAA-P1-06 — Protect employee documents
**Status:** IMPLEMENTED — metadata only; storage integration pending.

As an authorized HR user, I want employee documents stored privately with classification and retention controls so that sensitive records are not exposed through public links or general employee access.

Acceptance criteria:
- Binary content resides in approved private storage, not the application database or public web root.
- Access uses short-lived authorized retrieval and is audited.
- Classification, version, expiry, retention, legal hold and deletion are enforced.
- Malware scanning and upload validation run before a document is available.
- Document access is separately permissioned and tested across organizations.

### ASAA-P1-07 — Validate timesheets and expense claims
**Status:** IMPLEMENTED — submission/review/reimbursement-reference workflows; policy and evidence controls pending.

As an employee and reviewer, I want timesheets and expense claims validated against approved project, time and expense rules so that finance receives accurate approved inputs.

Acceptance criteria:
- Project/task references are validated against authoritative records.
- Period boundaries, duplicate entries and approved time limits are enforced.
- Expense category, policy limits, duplicate claims and receipt evidence are checked.
- Approval and reimbursement recording are distinct; no bank transfer is implied.
- Finance export is reconciled and traceable.

### ASAA-P1-08 — Complete procurement and accounts payable
**Status:** NOT STARTED — supplier and purchase-request foundations.

As a procurement and finance user, I want approved requests to progress through quotations, purchase orders, receipt, invoice matching and payment review so that commitments and liabilities are controlled.

Acceptance criteria:
- Quotation comparison and approval authority are recorded.
- Purchase orders reference approved requests and suppliers.
- Receipt/acceptance records quantities and discrepancies.
- Invoice matching supports configurable two-/three-way matching and tolerances.
- Payment initiation is separately permissioned and reconciled with provider/bank confirmation.

### ASAA-P1-09 — Complete receivables and reconciliation
**Status:** IMPLEMENTED — customer/invoice/receipt foundation; remaining workflow pending.

As a finance user, I want receivables, adjustments and bank reconciliation linked to source records so that outstanding balances are accurate.

Acceptance criteria:
- Credit/debit notes, refunds, disputes and ageing are traceable to invoices.
- Receipt allocations prevent over-allocation and preserve unapplied amounts.
- Bank reconciliation distinguishes recorded receipts from confirmed settlement.
- Tax, numbering and e-invoice rules are enabled only after jurisdictional approval.
- Accounting exports reconcile to authoritative finance records.

### ASAA-P1-10 — Standardize shared workflow and notifications
**Status:** Not Started — selected domain-specific maker-checker flows exist.

As a workflow owner, I want consistent approvals, delegation, escalation, reminders and retry handling so that business work does not become stuck or bypass controls.

Acceptance criteria:
- Workflow definitions have version, owner, state graph and permission rules.
- Actions support submit, approve, reject, return, cancel, delegate and escalate where configured.
- Idempotency and optimistic concurrency prevent duplicate or stale decisions.
- Notification delivery status, retry and dead-letter handling are observable.
- Domain-specific authorization and audit semantics remain authoritative.

## P2 — Enterprise expansion

- **ASAA-P2-01 Recruitment:** vacancies, candidate pipeline, interviews, evaluation and offer approvals.
- **ASAA-P2-02 Workforce development:** goals, performance, training, learning and certification records.
- **ASAA-P2-03 Employee relations:** restricted grievances, investigations, appeals and corrective actions.
- **ASAA-P2-04 CRM and sales:** leads, accounts, contacts, pipeline, proposals, contracts and renewals.
- **ASAA-P2-05 Projects and products:** portfolio, dependencies, budgets, requirements, milestones, product lifecycle and releases.
- **ASAA-P2-06 Delivery and support:** service catalogue, work orders, SLAs, support queues, incidents and customer feedback.
- **ASAA-P2-07 Inventory and facilities:** stock, assets, maintenance, facilities, travel and logistics.
- **ASAA-P2-08 Knowledge and collaboration:** controlled knowledge, announcements, calendars, meetings, decisions and action items.
- **ASAA-P2-09 Analytics and AI:** governed KPIs, source lineage, forecasting and permission-aware AI-assisted search/recommendations.

## Current-cycle implementation log

- Refined the requirements gap register and added explicit P0/P1/P2 delivery boundaries.
- Started ASAA-P1-01: organization-scoped payroll period uniqueness and non-overlapping date-window validation.
- No production database, identity provider, payroll policy, statutory rules or deployment environment is assumed.


## Release-closure backlog — remaining work as of 2026-11-13

This section consolidates the outstanding work required to turn the current executable slice into a controlled first production release. Existing story statuses above remain authoritative for their individual capabilities. A story is not complete until its acceptance evidence is attached to the release record.

### P0 — Production release gates

#### ASAA-P0-08 — Provision and validate the production database
**Status:** NEEDS TESTING — target environment and credentials are not provisioned. PostgreSQL 16 migration/API integration CI is passing; this is not production validation.

Acceptance criteria:
- Approve hosting region, residency, network boundary, PostgreSQL service/version and environment ownership.
- Provision separate development, staging and production databases with encryption at rest and certificate-verified TLS.
- Create separate migration and runtime roles; prove runtime cannot own/alter schema, create roles/databases or bypass row-level security.
- Configure connection limits, pool sizing, statement/idle timeouts, storage alerts and secret rotation.
- Run Alembic migration rehearsal and `scripts/validate_postgresql.py` against the actual production target; retain redacted output and revision evidence.
- Run production-like concurrency/load and migration compatibility checks; resolve all failures before release.

#### ASAA-P0-09 — Select and activate the identity provider
**Status:** OWNER ACCEPTANCE PENDING — provider, tenant and client configuration not selected.

Acceptance criteria:
- Record approved provider, tenant, issuer, API audience, public SPA client, redirect/logout URIs and JWKS endpoint.
- Configure Authorization Code + PKCE (S256), state/nonce handling as applicable, issuer/audience/signature/expiry validation and key rotation.
- Enforce MFA in provider policy and verify the required assurance/method claims with positive and negative tests.
- Validate login, logout, session expiry, refresh/revocation, account disablement and recovery paths in staging.
- Verify no client secret or long-lived sensitive token is exposed to or persisted by the browser.

#### ASAA-P0-10 — Synchronize identity lifecycle and effective access
**Status:** NOT STARTED — provider adapter and authoritative identity mapping not implemented/configured.

Acceptance criteria:
- Define stable person-to-provider subject mapping and joiner/mover/leaver event ownership.
- Implement idempotent provisioning, update, disablement and revocation through supported provider APIs/SCIM where available.
- Translate only independently approved, effective-dated role/scope assignments into effective entitlements.
- Reconcile ASAA access records against provider state and surface drift, failed actions and retry/dead-letter outcomes.
- Demonstrate timely access removal, session invalidation and emergency access expiry/review.
- Prove that governance/access-review records alone do not grant permissions before synchronization succeeds.

#### ASAA-P0-11 — Complete production authorization and security assurance
**Status:** IMPLEMENTED — baseline controls exist; comprehensive release evidence pending.

Acceptance criteria:
- Build a permission matrix for every API route and sensitive UI action, including read, write, export, approve, administer and lifecycle transitions.
- Pass positive and negative tests for organization isolation, record/field scope, HR/payroll separation, privileged access and horizontal/vertical escalation.
- Verify maker-checker, self-approval prevention, delegation scope/expiry/revocation and stale-version/idempotency behavior.
- Complete threat model, data classification, privacy/jurisdiction review, dependency and static analysis, dynamic/API testing and independent penetration testing appropriate to exposure.
- Protect audit history against unauthorized modification; alert on audit-write failure and sensitive access anomalies.
- Record findings, severity, owner, remediation, retest and explicit residual-risk acceptance.

#### ASAA-P0-12 — Establish production operations and recovery
**Status:** NOT STARTED — — hosting, monitoring and recovery objectives require owner decisions.

Acceptance criteria:
- Approve RPO, RTO, backup retention, data residency, support hours and incident escalation ownership.
- Configure encrypted automated backups, point-in-time recovery where supported, backup-failure alerts and isolated restore tests.
- Configure centralized structured logs, metrics, traces, health checks, alert routing and runbooks without sensitive-data leakage.
- Establish production secret management, key rotation, vulnerability response, incident handling and audit retention.
- Automate reviewed build, migration and deployment stages; separate migration credentials from runtime credentials.
- Exercise deployment, smoke tests, rollback/forward recovery and disaster recovery; record measured outcomes.

#### ASAA-P0-13 — Approve first-release business acceptance
**Status:** OWNER ACCEPTANCE PENDING — named business owners and approved operating policies required.

Acceptance criteria:
- Confirm launch scope, organization/legal entity context, data owners, authorized users and support owners.
- Approve role matrix, approval limits, leave rules, payroll inputs, expense/procurement rules, document retention and applicable jurisdictional requirements.
- Complete scripted UAT for organization/governance, employee lifecycle, leave, compensation/payroll controls, supplier/AP, customer/AR, timesheets and expenses.
- Use synthetic or approved minimized test data; prove demo/test data cannot be mistaken for production records.
- Resolve release-blocking defects; obtain documented business, security and operations sign-off.

### P1 — Complete coherent first-release workflows

#### ASAA-P1-11 — Complete AP procure-to-pay
**Status:** NOT STARTED — supplier and purchase-request foundations.

Acceptance criteria: quotation capture/comparison; approved purchase orders; receipt and discrepancy handling; configurable two-/three-way invoice matching; duplicate invoice prevention; approval limits; payment instruction separation; provider/bank settlement reconciliation; auditable exceptions and finance export.

#### ASAA-P1-12 — Complete AR and cash reconciliation
**Status:** IMPLEMENTED — initial customer/invoice/receipt foundation; end-to-end acceptance pending.

Acceptance criteria: invoice lifecycle and adjustments; credit/debit notes, refunds and disputes; receipt allocation and unapplied cash; ageing; bank settlement reconciliation; tax/e-invoice rules only after jurisdictional approval; traceable accounting export.

#### ASAA-P1-13 — Complete workforce policy and operational controls
**Status:** IMPLEMENTED — core HR/leave/onboarding/offboarding views and API foundations; policy and integration validation pending.

Acceptance criteria: approved effective-dated employment and leave policies; balance/holiday/accrual rules; task ownership, reminders and escalation; asset issue/return evidence; offboarding handover and access-revocation confirmation; employee history and audit review.

#### ASAA-P1-14 — Complete payroll control workflow without assuming statutory rules
**Status:** IN DEVELOPMENT — compensation and payroll control foundations exist; input lineage, exception and business validation remain.

Acceptance criteria: source-linked payroll inputs; duplicate and currency validation; decimal-safe gross/deduction/net reconciliation; versioned approved calculation rules; independent review/closure; restricted payslip/output access; payment execution kept as a separate integration; no statutory calculation until jurisdiction-specific rules are approved and independently tested.

#### ASAA-P1-15 — Integrate private documents and notifications
**Status:** NOT STARTED — — storage and delivery providers not selected.

Acceptance criteria: private object storage, short-lived authorized access, malware/upload validation, classification/version/retention/legal hold, access audit; notification templates/preferences, delivery status, retries, dead-letter visibility and sensitive-content minimization.

#### ASAA-P1-16 — Standardize workflow orchestration and integration operations
**Status:** Not Started — selected domain workflows exist; reusable shared services and operational visibility remain.

Acceptance criteria: versioned workflow definitions, common transition semantics, idempotent commands, concurrency controls, delegation/escalation, integration registry, scoped credentials, sync history, retry/reconciliation and actionable health dashboards.

#### ASAA-P1-17 — Complete end-to-end quality and accessibility validation
**Status:** NEEDS TESTING — — comprehensive release evidence not recorded.

Acceptance criteria: automated unit, API, database migration, UI, end-to-end, regression, security, performance and accessibility coverage for launch workflows; supported browser/device checks; keyboard and screen-reader review; documented test environment, revision, results and defect disposition.

### Release exit rule

The first production release is blocked until every P0 story above is Passed or has an explicitly approved, documented exception that does not weaken security, legal compliance, data integrity or recovery. P1 stories must be either accepted in the launch scope with Passed evidence or explicitly excluded/disabled with clear user-facing boundaries. P2 expansion stories remain outside the first-release gate unless the owner brings them into scope.


## Status source

For current cross-project maturity, P0/P1/P2 gaps, release decision and evidence, refer to [Project Status](PROJECT_STATUS.md). This story backlog retains detailed capability acceptance criteria; it is not a second project-wide status register.


## Verified security-hardening increment — 2026-11-13

**Status:** CI VERIFIED — commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c`, web CI run [43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233).

The browser OIDC client now applies the HTTPS policy to the JWKS endpoint as well as the authorization and token endpoints. Four Node.js regression tests cover HTTPS acceptance, local-development HTTP exceptions, remote HTTP rejection and non-HTTP scheme rejection. This closes the JWKS transport-validation code gap only; it does not close provider selection, tenant activation, MFA policy, identity lifecycle or full SSO acceptance.
