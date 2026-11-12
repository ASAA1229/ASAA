# ASAA Enterprise Operating Platform — Enterprise User Story Map

**Status:** Initial owner-review backlog; not implementation-completion evidence  
**Source of truth for target scope:** `docs/ENTERPRISE_OPERATING_MODEL.md`  
**Technology policy:** Technology-stack independent

This backlog expands the original project-intelligence stories into the complete internal operating platform. Stories are grouped by business capability. Department policies, legal rules, payroll calculations, tax rules, approval limits and integrations remain unresolved until explicitly confirmed by the organization owner.

## Priority convention

- **P0 — Foundation:** required before dependent business modules can be safely operated.
- **P1 — First operating releases:** high-value internal business operations.
- **P2 — Expansion:** additional enterprise capabilities after foundations and core workflows are validated.

## Epic A — Organization, governance and administration

### ASAA-ORG-001 — Configure organization structure
**Priority:** P0  
As the organization owner, I want to configure the organization, business units, divisions, departments, teams and locations so that the platform reflects the real company structure.

Acceptance criteria:
- Structure is configurable and does not assume every unit exists at launch.
- Effective dates, owners, parent-child relationships and history are recorded.
- Reorganizations do not erase historical reporting relationships.
- Users can be associated with more than one team or unit where authorized.

### ASAA-ORG-002 — Manage people and organizational membership
**Priority:** P0  
As an authorized administrator, I want a central directory of employees and external collaborators so that identities and organizational relationships are managed consistently.

Acceptance criteria:
- Distinguish employees, contractors, interns, freelancers, clients, vendors and other collaborators.
- Store only necessary personal data with field-level/scope-sensitive access.
- Track active, pending, suspended and former relationships.
- Preserve history and audit changes.

### ASAA-ORG-003 — Configure roles and permissions
**Priority:** P0  
As the organization owner, I want configurable roles, permissions and data scopes so that every person sees and performs only what their responsibilities permit.

Acceptance criteria:
- Job title, reporting line, approval authority and application role are distinct.
- Support role assignment by organization, business unit, department, team and record scope.
- Enforce authorization on every server-side operation and export.
- Sensitive permissions can require MFA, re-authentication or additional approval.
- Access grants, changes, reviews and revocations are audited.

### ASAA-ORG-004 — Configure approval authority and separation of duties
**Priority:** P0  
As the organization owner, I want configurable approval matrices and authority limits so that critical decisions are properly controlled.

Acceptance criteria:
- Workflows support one or more approval steps, delegation, rejection, return-for-correction and escalation.
- Rules can depend on department, amount, record type or risk.
- Maker-checker rules prevent prohibited self-approval.
- Every decision records actor, time, outcome and rationale.

### ASAA-ORG-005 — Maintain organization policies and procedures
**Priority:** P1  
As an authorized policy owner, I want to publish versioned policies and procedures so that staff use approved and current rules.

Acceptance criteria:
- Policies have owners, versions, effective dates, review dates and approval history.
- Acknowledgements are recorded when required.
- Superseded policies remain available to authorized reviewers.

## Epic B — Shared platform foundations

### ASAA-CORE-001 — Configure shared reference data
**Priority:** P0  
As an administrator, I want controlled lists for currencies, locations, departments, employment types, statuses and other reference data so that modules use consistent values without hard-coded assumptions.

### ASAA-CORE-002 — Manage workflows and business states
**Priority:** P0  
As a process owner, I want configurable state transitions and approval workflows so that business processes can be adapted without redesigning the whole platform.

### ASAA-CORE-003 — Maintain audit history
**Priority:** P0  
As an owner or authorized auditor, I want traceable history for sensitive and important actions so that changes and decisions remain accountable.

Acceptance criteria:
- Capture actor, timestamp, action, target, scope, outcome and correlation reference.
- Preserve before/after context where appropriate and lawful.
- Do not log passwords, tokens, bank details or unnecessary sensitive payloads.
- Restrict audit access and prevent ordinary users from rewriting audit history.

### ASAA-CORE-004 — Manage documents and records
**Priority:** P0  
As an authorized user, I want to attach, classify, version and retrieve documents so that business records remain organized and permissioned.

### ASAA-CORE-005 — Send notifications and reminders
**Priority:** P1  
As a user, I want relevant task, approval, deadline and policy notifications so that actions are not missed.

### ASAA-CORE-006 — Register and monitor integrations
**Priority:** P0  
As an integration administrator, I want provider adapters with scoped credentials, health, sync history and error handling so that external systems can connect without coupling the ASAA core to one vendor.

### ASAA-CORE-007 — Search and export authorized records
**Priority:** P1  
As an authorized user, I want to search and export records within my access scope so that information can be found and used without bypassing permissions.

## Epic C — Employee lifecycle and HR

### ASAA-HR-001 — Create and maintain employee profiles
**Priority:** P0  
As an HR administrator, I want a secure employee profile with employment, department, position, manager and contact information so that employee records are centrally maintained.

### ASAA-HR-002 — Manage recruitment and candidate records
**Priority:** P2  
As an authorized recruiter, I want to manage vacancies, candidates, interviews and offers so that recruitment is traceable.

### ASAA-HR-003 — Manage onboarding
**Priority:** P1  
As HR, I want configurable onboarding checklists, document collection, asset assignment and access requests so that new joiners are prepared consistently.

### ASAA-HR-004 — Manage employment changes
**Priority:** P1  
As HR, I want to record transfers, promotions, manager changes, contract changes and status changes with effective dates and approvals.

### ASAA-HR-005 — Manage offboarding
**Priority:** P1  
As HR, I want a controlled exit workflow covering handover, assets, final settlement inputs, document retention and access revocation.

### ASAA-HR-006 — Manage employee documents
**Priority:** P1  
As HR, I want restricted employee document storage, expiry reminders and acknowledgement tracking so that records are maintained securely.

### ASAA-HR-007 — Manage employee requests and grievances
**Priority:** P2  
As an employee, I want to submit confidential HR requests or grievances and track their authorized handling.

## Epic D — Attendance, leave and schedules

### ASAA-WFM-001 — Configure attendance policies
**Priority:** P0  
As the organization owner/HR policy owner, I want configurable working calendars, grace periods, break rules, shift rules and attendance policies so that attendance behavior reflects approved company policy.

### ASAA-WFM-002 — Record check-in and check-out
**Priority:** P1  
As an employee, I want to record work start/end and permitted breaks through approved channels so that attendance records are available.

Acceptance criteria:
- Support configurable web/mobile/manual/device-based capture channels.
- Store event time, recorded time, source and correction history.
- Handle missed punches and duplicate/offline submissions.
- Do not silently alter original attendance events.
- Location/device verification is optional, proportionate and explicitly policy-controlled; no covert tracking.

### ASAA-WFM-003 — Review daily attendance
**Priority:** P1  
As an employee and manager, I want to view attendance records and exceptions so that errors can be identified and corrected.

### ASAA-WFM-004 — Request attendance correction
**Priority:** P1  
As an employee, I want to request correction of missing or incorrect attendance with a reason and evidence so that records can be reviewed fairly.

### ASAA-WFM-005 — Configure leave types and policies
**Priority:** P0  
As an authorized HR policy owner, I want to configure leave categories, eligibility, accrual, carry-forward, expiry, holidays and balance rules so that leave is governed by approved company policy.

Acceptance criteria:
- Leave rules are versioned and effective-dated.
- Do not assume statutory or contractual entitlements before jurisdiction and policy are confirmed.
- Support paid, unpaid, annual, casual, sick, special and organization-defined leave types as configurable categories.
- Maintain a traceable leave ledger rather than silently overwriting balances.

### ASAA-WFM-006 — Apply for leave
**Priority:** P1  
As an employee, I want to view my available leave information and submit, amend or cancel a leave request so that absence is formally recorded.

### ASAA-WFM-007 — Review and approve leave
**Priority:** P1  
As an authorized manager/HR reviewer, I want to approve, reject or request clarification on leave requests so that team availability and policy are managed.

### ASAA-WFM-008 — Manage holidays and work calendars
**Priority:** P1  
As an administrator, I want calendars by applicable location, team or work pattern so that working days and holidays are calculated correctly.

### ASAA-WFM-009 — Manage shifts and rosters
**Priority:** P1  
As an operations manager, I want to assign fixed, rotating or flexible shifts and manage swaps so that staffing coverage is visible.

### ASAA-WFM-010 — Manage overtime and compensatory time
**Priority:** P2  
As an authorized manager/HR reviewer, I want overtime or compensatory-time records reviewed under approved policies so that additional work is traceable.

### ASAA-WFM-011 — View team availability
**Priority:** P1  
As a manager, I want an access-controlled view of team attendance, approved leave, shifts and availability so that work can be planned.

## Epic E — Work logs, timesheets and capacity

### ASAA-WORK-001 — Record daily work logs
**Priority:** P1  
As an employee, I want to record work performed, outcomes, blockers and relevant references so that work progress is visible.

### ASAA-WORK-002 — Allocate work to projects and activities
**Priority:** P1  
As a manager, I want work logs linked to authorized projects, products, clients or internal activities so that effort has business context.

### ASAA-WORK-003 — Submit timesheets
**Priority:** P1  
As an employee, I want to submit daily or weekly timesheets for review so that recorded hours can be validated.

### ASAA-WORK-004 — Review and approve timesheets
**Priority:** P1  
As an authorized manager, I want to review, return or approve timesheets with a rationale so that downstream reporting and billing inputs are controlled.

### ASAA-WORK-005 — View capacity and workload
**Priority:** P2  
As a department head, I want authorized capacity and workload reports so that assignments can be balanced.

Acceptance criteria for this epic:
- Attendance duration and task/work-log duration remain distinct concepts.
- Time records are not automatically treated as proof of productivity.
- Corrections retain history and approval.
- Client-billable and internal hours are explicitly classified.

## Epic F — Compensation, payroll and benefits

### ASAA-PAY-001 — Maintain compensation records
**Priority:** P1  
As an authorized HR/Finance user, I want restricted, effective-dated compensation records so that salary changes are traceable.

### ASAA-PAY-002 — Prepare payroll inputs
**Priority:** P2  
As an authorized payroll operator, I want approved attendance, leave, overtime, compensation and deduction inputs assembled for payroll review.

### ASAA-PAY-003 — Review and reconcile payroll
**Priority:** P2  
As an authorized payroll approver, I want payroll totals and exceptions reviewed before finalization so that errors can be corrected.

### ASAA-PAY-004 — Manage payslips and payroll history
**Priority:** P2  
As an employee, I want secure access to my own payslips and payroll history.

### ASAA-PAY-005 — Manage benefits and reimbursements
**Priority:** P2  
As an employee, I want to submit eligible benefit and reimbursement claims and track their approval and settlement.

Safeguards:
- Payroll, tax, statutory deductions and payslip formats depend on confirmed legal jurisdiction and approved policies.
- Salary and banking data are restricted to explicitly authorized roles.
- Payroll calculation or payment execution must not be enabled without reconciliation, approval and audit controls.

## Epic G — Projects, products, engineering and QA

### ASAA-PPM-001 — Manage organization portfolio and projects
**Priority:** P1  
As the organization owner, I want a portfolio of projects with owners, goals, milestones, risks and evidence-backed status so that I can oversee delivery.

### ASAA-PPM-002 — Manage requirements and changes
**Priority:** P1  
As a product/project owner, I want versioned requirements, acceptance criteria and change approvals so that scope is controlled.

### ASAA-PROD-001 — Manage product catalogue and lifecycle
**Priority:** P1  
As a product owner, I want products, versions, features, roadmaps, release status and retirement records managed centrally.

### ASAA-ENG-001 — Manage engineering delivery references
**Priority:** P1  
As an engineering lead, I want repositories, environments, build metadata and release references linked to products/projects without imposing a common technology stack or workflow.

### ASAA-QA-001 — Manage quality and testing
**Priority:** P1  
As a QA lead, I want test plans, test cases, test runs, defects, evidence and release gates so that product quality is measurable.

### ASAA-REL-001 — Govern releases and deployments
**Priority:** P1  
As an authorized release owner, I want release approvals, deployment evidence, rollback plans and environment history so that releases are controlled.

## Epic H — Services, clients and commercial operations

### ASAA-CRM-001 — Manage customers and leads
**Priority:** P1  
As a sales owner, I want customer accounts, contacts, leads and opportunity history so that commercial relationships are managed.

### ASAA-SALES-001 — Manage proposals and quotations
**Priority:** P1  
As an authorized sales user, I want estimates, proposals, quotations and approval history so that offers are controlled.

### ASAA-COM-001 — Manage products, services and pricing
**Priority:** P1  
As an authorized commercial owner, I want configurable price lists, pricing versions, discounts, packages and effective dates so that commercial terms are consistent.

### ASAA-COM-002 — Manage contracts and orders
**Priority:** P1  
As an authorized user, I want contracts, statements of work, orders, renewals and obligations linked to customers and delivery work.

### ASAA-SVC-001 — Manage service delivery and support
**Priority:** P1  
As an operations/service manager, I want service requests, assignments, SLAs, escalations and closure evidence so that commitments are tracked.

## Epic I — Finance, billing and accounting

### ASAA-FIN-001 — Manage budgets and cost centres
**Priority:** P1  
As an authorized finance owner, I want budgets, cost centres and project allocations so that spending can be planned and controlled.

### ASAA-FIN-002 — Create and manage invoices
**Priority:** P1  
As an authorized finance user, I want invoices linked to customers, contracts, orders or approved milestones so that billing is traceable.

### ASAA-FIN-003 — Track receivables and receipts
**Priority:** P1  
As an authorized finance user, I want to track amounts due, receipts, overdue balances and reconciliation status.

### ASAA-FIN-004 — Manage vendor bills and payables
**Priority:** P2  
As an authorized finance user, I want supplier bills, due dates, approvals and payment status recorded.

### ASAA-FIN-005 — Manage expenses and reimbursements
**Priority:** P1  
As an employee, I want to submit expense claims with receipts and business purpose so that eligible expenses can be reviewed and reimbursed.

### ASAA-FIN-006 — Produce financial reports
**Priority:** P2  
As an authorized executive/finance user, I want controlled revenue, cost, margin, cash-flow and budget reports with traceable source records.

Safeguards:
- Accounting, tax, invoice numbering, e-invoicing and statutory reports depend on confirmed company registration and jurisdiction.
- Financial transactions require permissions, validation, approval and immutable audit history.
- No real payment execution without separately approved provider integration and controls.

## Epic J — Procurement, vendors and assets

### ASAA-OPS-001 — Manage vendors and suppliers
**Priority:** P2  
As an authorized procurement user, I want supplier profiles, contracts, performance and compliance records.

### ASAA-OPS-002 — Manage purchase requests and orders
**Priority:** P2  
As an employee/manager, I want purchase requests reviewed against budgets and authority limits before orders are issued.

### ASAA-OPS-003 — Manage organizational assets
**Priority:** P1  
As an asset administrator, I want equipment assignment, custody, warranty, maintenance and return records so that company assets are accountable.

### ASAA-OPS-004 — Manage inventory
**Priority:** P2  
As an operations user, I want stock, movements, reorder levels and reconciliations where inventory is part of the business.

## Epic K — Legal, compliance, security and risk

### ASAA-GRC-001 — Maintain legal and compliance obligations
**Priority:** P2  
As an authorized compliance owner, I want obligations, evidence, owners, deadlines and review history so that requirements can be monitored.

### ASAA-GRC-002 — Manage organizational risks and incidents
**Priority:** P1  
As an owner or risk manager, I want risks, incidents, mitigations and impact links across departments so that threats are visible and managed.

### ASAA-GRC-003 — Manage access reviews
**Priority:** P1  
As an organization owner/security administrator, I want periodic access reviews and revocation workflows so that permissions remain appropriate.

### ASAA-GRC-004 — Manage privacy and retention requests
**Priority:** P2  
As an authorized privacy owner, I want data classification, retention schedules and privacy request workflows so that personal information is governed.

## Epic L — Knowledge, communication and collaboration

### ASAA-KNOW-001 — Maintain organizational knowledge
**Priority:** P1  
As an employee, I want an authorized searchable knowledge base with document ownership and version history so that approved knowledge can be reused.

### ASAA-COMMS-001 — Publish announcements
**Priority:** P1  
As an authorized communicator, I want to target announcements by organization, department or team and track required acknowledgements.

### ASAA-MEET-001 — Manage meetings and action items
**Priority:** P2  
As a team member, I want meeting records, decisions and assigned action items linked to relevant work.

## Epic M — Executive intelligence and governed automation

### ASAA-EXEC-001 — Provide an executive command centre
**Priority:** P1  
As the organization owner/CEO, I want a role-secured overview of organizational performance, exceptions, approvals, cash/financial summaries, workforce, products, delivery and risks.

Acceptance criteria:
- Every metric has a definition, source, owner, period and refresh time.
- Unknown or stale data is visibly identified.
- Drill-down respects source-record permissions.
- Cross-domain totals reconcile to authoritative records.

### ASAA-EXEC-002 — Configure KPIs and alerts
**Priority:** P2  
As a department head, I want approved KPIs, targets and exception alerts so that performance can be monitored transparently.

### ASAA-AI-001 — Provide governed AI assistance
**Priority:** P2  
As an authorized user, I want AI assistance to search, summarize and recommend actions using only permitted information so that routine work is faster.

### ASAA-AUTO-001 — Automate approved workflows
**Priority:** P2  
As a process owner, I want approved triggers and actions with scopes, approvals, logs and failure handling so that repeatable operations can be automated safely.

Acceptance criteria:
- Every automation has an owner, purpose, permissions and enabled state.
- High-impact actions require human approval.
- Execution is traceable and idempotent where possible.
- Failure, retry, disablement and recovery are defined.
- AI/automation cannot bypass access controls or approval policy.

## Epic N — Reliability, privacy and platform operations

### ASAA-PLAT-001 — Protect organizational data
**Priority:** P0  
As the organization owner, I want encryption, access boundaries, secure secret handling and privacy controls so that organizational data is protected.

### ASAA-PLAT-002 — Back up and restore organizational records
**Priority:** P0  
As a platform operator, I want tested backups and restoration procedures so that the organization can recover from failures.

### ASAA-PLAT-003 — Monitor platform health
**Priority:** P0  
As a platform operator, I want service health, integration failures, queues, storage and security events monitored without exposing sensitive information.

### ASAA-PLAT-004 — Export organizational data
**Priority:** P1  
As the organization owner, I want documented exports of key business records in usable formats so that ASAA retains data portability and avoids vendor lock-in.

## Initial implementation order

1. **Foundation:** ASAA-ORG-001 to 005, ASAA-CORE-001 to 007, ASAA-PLAT-001 to 004.
2. **Workforce first release:** ASAA-HR-001, ASAA-WFM-001, ASAA-WFM-005, followed by attendance, leave, shift and work-log workflows.
3. **Daily operating workflows:** ASAA-WORK-001 to 004, internal requests, documents and notifications.
4. **Project/product/QA operations:** portfolio, requirements, product lifecycle, engineering references, testing and releases.
5. **Commercial/finance:** customer, pricing, contracts, invoices, receipts, budgets and expenses.
6. **Operational and governance expansion:** procurement, vendors, assets, compliance, security, knowledge and analytics.
7. **Advanced intelligence:** governed AI and automation after permissions, audit and rollback foundations pass validation.

## Definition of done for every story

- Owner and authorized user roles are defined.
- Business policy and record ownership are confirmed.
- Functional and negative acceptance criteria are testable.
- Privacy classification and access boundaries are specified.
- Audit events and history behavior are specified.
- Integration contracts and failure handling are defined where relevant.
- Automated/manual verification evidence exists.
- Documentation, known limitations and operational ownership are updated.
- The story is not called complete merely because UI or code exists.


## Organization hierarchy and department setup — detailed story expansion

The full catalogue and rules are defined in `docs/ORGANIZATION_HIERARCHY_AND_DEPARTMENTS.md`.

### ASAA-ORG-006 — Maintain department catalogue
**Priority:** P0  
As the organization owner, I want to activate, configure, combine, rename, split, deactivate and archive departments so that ASAA reflects the actual company and can grow without schema redesign.

Acceptance criteria:
- Department records include purpose, responsibilities, owner, parent unit, status and effective dates.
- Departments may be planned, active, inactive or archived.
- The system does not force all catalogue departments to exist.
- Historical department membership and reports remain accurate after reorganizations.

### ASAA-ORG-007 — Configure reporting relationships
**Priority:** P0  
As an organization administrator, I want primary, secondary, matrix and temporary reporting relationships so that formal HR management is distinct from project delivery coordination.

Acceptance criteria:
- Relationships have type, scope, effective start/end and history.
- Temporary acting assignments expire or require renewal.
- Matrix/project leads do not automatically gain HR, salary or confidential employee access.
- Circular or invalid primary reporting relationships are rejected or explicitly reviewed.

### ASAA-ORG-008 — Manage positions and job families
**Priority:** P1  
As an HR administrator, I want configurable positions, job families, grades and title conventions so that the company can define career and staffing structures without hard-coded rank assumptions.

Acceptance criteria:
- Job title, job family, grade, position, system role and approval authority remain distinct.
- Position vacancies and assignments are tracked.
- One person may hold multiple effective-dated assignments where approved.

### ASAA-ORG-009 — View and validate organization chart
**Priority:** P1  
As the organization owner, I want an interactive organization chart and department directory so that I can inspect reporting lines, ownership gaps and organizational structure.

Acceptance criteria:
- Views can be filtered by entity, business unit, division, department and location.
- Historical "as of date" views are supported.
- Unassigned department ownership and vacant positions are visible.
- Export and drill-down respect access permissions.

### ASAA-ORG-010 — Preview effective permissions
**Priority:** P0  
As an organization/security administrator, I want to preview what a user can view and do before granting or changing access so that role assignments do not accidentally expose sensitive records.

Acceptance criteria:
- Preview considers role, scope, memberships, explicit grants and policy restrictions.
- Sensitive data access is shown separately from general department visibility.
- Access changes are audited and can be reviewed after assignment.
