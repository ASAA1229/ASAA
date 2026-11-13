# ASAA User Stories and Acceptance Backlog

**Product:** Internal ASAA Enterprise Operating Platform  
**Baseline branch:** `new`  
**Backlog status:** Refined from the current repository implementation and documented operational evidence  
**Rule:** Built code is not automatically Verified. Provider, policy, jurisdiction and infrastructure decisions remain explicit dependencies.

## Status vocabulary

- **Built / Passed:** implementation and identified verification evidence exist.
- **Built — verification pending:** code exists but the current acceptance evidence is incomplete.
- **In Progress:** implementation has started in the current cycle.
- **Not Started:** no implementation evidence.
- **Blocked:** a required owner decision, external provider, policy or environment is unavailable.
- **Deferred:** intentionally scheduled for a later release.

## P0 — Production foundation and governance

### ASAA-P0-01 — Operate PostgreSQL safely
**Status:** Built — CI passed; production validation blocked by environment provisioning.

As a platform operator, I want a production PostgreSQL deployment with verified transport security, least-privilege roles, migration controls and capacity limits so that organizational records are stored safely.

Acceptance criteria:
- PostgreSQL 16+ is provisioned in an approved environment with certificate-verified TLS.
- Migration identity is separate from the runtime identity.
- Runtime identity cannot own application schema/tables, create roles/databases, bypass RLS or alter schema.
- Production preflight passes against the actual target; secrets and database URLs are redacted.
- Connection pool limits, timeouts, capacity and load behaviour are measured.
- Migration rehearsal, backup and recovery evidence is attached to the release.

### ASAA-P0-02 — Recover the platform
**Status:** Not Started / Blocked — RPO, RTO, retention and hosting decisions required.

As an operations owner, I want encrypted backups, point-in-time recovery and rehearsed restore procedures so that service and data can be recovered after failure.

Acceptance criteria:
- Approved RPO, RTO, retention and residency requirements are recorded.
- Automated backups and backup-failure alerts are enabled.
- Restore is demonstrated in an isolated environment.
- Database and document/object metadata consistency is checked.
- Recovery steps, owners, measured recovery time and residual risks are recorded.

### ASAA-P0-03 — Authenticate with real SSO and MFA
**Status:** Built — OIDC/RS256/JWKS foundations; provider integration Blocked.

As an employee, I want to sign in through the approved identity provider with enforced MFA so that I use one managed identity securely.

Acceptance criteria:
- Provider, tenant, issuer, API audience, public SPA client and exact redirect URIs are approved.
- Authorization Code + PKCE (S256), state validation, issuer/audience/signature/expiry and signing-key rotation are tested.
- MFA assurance is enforced by provider policy and validated using documented claims.
- Logout, refresh/revocation, account disablement and recovery paths are tested.
- No client secret or long-lived sensitive token is shipped or persisted in browser storage.

### ASAA-P0-04 — Provision and revoke identities
**Status:** Not Started / Blocked — provider selection and authoritative identity mapping required.

As an authorized administrator, I want employee lifecycle and approved access assignments synchronized with the identity provider so that access is granted and removed at the correct time.

Acceptance criteria:
- Joiner, mover and leaver events map to provider account lifecycle operations.
- Role/scope assignments are derived only from approved, effective-dated records.
- Expired and revoked assignments remove effective access within an approved service target.
- Reconciliation identifies drift between ASAA and provider state.
- Failed provisioning/revocation is visible, retried safely and escalated.
- Emergency access is time-limited, justified and independently reviewed.

### ASAA-P0-05 — Enforce governance and authority
**Status:** Built — register/workflows exist; enforcement integration pending.

As an organization owner, I want organizational units, decision authority, delegations and role assignments validated against authoritative people and scope records so that approval rights cannot be inferred from titles or stale references.

Acceptance criteria:
- Organization units and master-data references are validated and effective-dated.
- Delegations identify permitted actions, scope, limits, start/end and independent reviewer.
- Self-approval and invalid scope/subject references are rejected.
- Policy evaluation honours effective dates, expiry and revocation.
- Every decision and change is auditable.
- Register records do not grant API/provider access until the enforcement adapter is active.

### ASAA-P0-06 — Prove security and audit controls
**Status:** Built — baseline controls exist; production assurance pending.

As a security owner, I want authorization, privacy, audit and incident controls tested so that sensitive employee and financial data is protected.

Acceptance criteria:
- Positive and negative permission tests cover every sensitive read/write/export/approval path.
- Cross-organization and horizontal/vertical privilege escalation tests pass.
- Audit records include actor, organization, target, action, timestamp, outcome and correlation ID.
- Audit failure is not silently ignored for protected decisions.
- Threat model, data classification, privacy review, dependency/security testing and incident exercise are approved.
- Production logs and errors do not expose tokens, secrets or restricted personal/financial data.

### ASAA-P0-07 — Operate and observe releases
**Status:** Not Started / Blocked — hosting and monitoring provider decisions required.

As an operator, I want observable services and controlled releases so that failures are detected and changes can be recovered safely.

Acceptance criteria:
- Structured logs, metrics, traces and alert routing are configured.
- Alerts have severity, owner, runbook and escalation.
- Production migrations run through a controlled job with a migration-only identity.
- Releases identify commit, artifact, migration revision and approvals.
- Smoke tests and rollback/forward-recovery procedures are exercised.

## P1 — Finance, payroll and workforce

### ASAA-P1-01 — Prevent overlapping payroll periods
**Status:** In Progress — first implementation slice in this cycle.

As a payroll administrator, I want payroll periods to have unique organization-scoped codes and non-overlapping date ranges so that employees cannot be included in duplicate or conflicting periods.

Acceptance criteria:
- Start date cannot follow end date.
- A period code cannot be reused within an organization; API returns a controlled conflict.
- Any date intersection with an existing period in the same organization is rejected with a stable conflict code.
- Adjacent non-overlapping periods are accepted.
- Another organization may use the same code/date range.
- Automated tests cover duplicate, overlap, adjacency and organization isolation.

### ASAA-P1-02 — Maintain a valid compensation timeline
**Status:** Built — verification and correction workflow pending.

As a restricted payroll operator, I want effective-dated compensation records to be consistent and independently approved so that historical and future compensation cannot conflict.

Acceptance criteria:
- Effective intervals for an employee cannot conflict.
- Approved records cannot be silently overwritten.
- Corrections and supersession preserve original values and reasons.
- Currency, pay basis, frequency and effective dates are validated.
- Compensation read/write/approve permissions remain separate from general HR access.
- Maker-checker and audit tests pass.

### ASAA-P1-03 — Reconcile payroll inputs and outputs
**Status:** Built — supplied-input workflow exists; policy engine Blocked.

As a payroll reviewer, I want payroll inputs, gross, deductions and net amounts reconciled before approval so that errors are caught without inventing statutory calculations.

Acceptance criteria:
- Inputs identify their authoritative source and period.
- Duplicate employee entries and currency mismatches are rejected.
- Gross less deductions equals net using decimal-safe arithmetic.
- Changes after submission require return/resubmission and independent review.
- Approved rules are versioned and independently validated before any statutory calculation is enabled.
- Payment execution is a separate authorized integration.

### ASAA-P1-04 — Manage leave under approved policy
**Status:** Built — request/review; policy engine Not Started / Blocked.

As an employee, I want to request leave under published eligibility and balance rules so that I can understand available entitlement before submitting.

Acceptance criteria:
- Leave categories, holidays, working days, accrual and carry-forward are effective-dated and owner-approved.
- Balance calculations show source policy and calculation breakdown.
- Overlaps, insufficient balance and ineligible dates are rejected with actionable explanations.
- Manager/HR review, delegation, cancellation and correction are auditable.
- No balance or entitlement is fabricated before policy approval.

### ASAA-P1-05 — Complete employee lifecycle tasks
**Status:** Built — checklist foundations; automation pending.

As an HR/IT manager, I want onboarding and offboarding tasks assigned, due-dated and escalated so that access, equipment, handover and employee records are handled consistently.

Acceptance criteria:
- Templates are versioned and assignments retain a snapshot.
- Tasks have accountable owners, due dates, state, evidence and audit history.
- Required incomplete tasks block closure.
- Offboarding triggers approved identity/device revocation tasks and confirms completion from connected systems.
- Reminders, escalation and failed-action handling are visible.

### ASAA-P1-06 — Protect employee documents
**Status:** Built — metadata only; storage integration pending.

As an authorized HR user, I want employee documents stored privately with classification and retention controls so that sensitive records are not exposed through public links or general employee access.

Acceptance criteria:
- Binary content resides in approved private storage, not the application database or public web root.
- Access uses short-lived authorized retrieval and is audited.
- Classification, version, expiry, retention, legal hold and deletion are enforced.
- Malware scanning and upload validation run before a document is available.
- Document access is separately permissioned and tested across organizations.

### ASAA-P1-07 — Validate timesheets and expense claims
**Status:** Built — submission/review/reimbursement-reference workflows; policy and evidence controls pending.

As an employee and reviewer, I want timesheets and expense claims validated against approved project, time and expense rules so that finance receives accurate approved inputs.

Acceptance criteria:
- Project/task references are validated against authoritative records.
- Period boundaries, duplicate entries and approved time limits are enforced.
- Expense category, policy limits, duplicate claims and receipt evidence are checked.
- Approval and reimbursement recording are distinct; no bank transfer is implied.
- Finance export is reconciled and traceable.

### ASAA-P1-08 — Complete procurement and accounts payable
**Status:** Not Started beyond supplier and purchase-request foundations.

As a procurement and finance user, I want approved requests to progress through quotations, purchase orders, receipt, invoice matching and payment review so that commitments and liabilities are controlled.

Acceptance criteria:
- Quotation comparison and approval authority are recorded.
- Purchase orders reference approved requests and suppliers.
- Receipt/acceptance records quantities and discrepancies.
- Invoice matching supports configurable two-/three-way matching and tolerances.
- Payment initiation is separately permissioned and reconciled with provider/bank confirmation.

### ASAA-P1-09 — Complete receivables and reconciliation
**Status:** Built — customer/invoice/receipt foundation; remaining workflow pending.

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
