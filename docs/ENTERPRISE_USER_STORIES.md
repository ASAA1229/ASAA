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
**Implementation status:** Built Not Tested — organization-scoped employee profile creation, listing, detail, controlled profile updates and effective-dated lifecycle history; document management and broader employee lifecycle workflows remain open.
**Implementation status:** Built Not Tested — organization-scoped employee profiles and effective-dated employment records/history; employee lifecycle and full document management remain open.

### ASAA-HR-002 — Manage recruitment and candidate records
**Priority:** P2  
As an authorized recruiter, I want to manage vacancies, candidates, interviews and offers so that recruitment is traceable.

### ASAA-HR-003 — Manage onboarding
**Priority:** P1  
As HR, I want configurable onboarding checklists, document collection, asset assignment and access requests so that new joiners are prepared consistently.
**Implementation status:** Built Not Tested — reusable templates, assignment snapshots, task status/evidence and completion tracking; document, asset and access-provisioning integrations remain open.
**Implementation status:** Built Not Tested — reusable templates, employee assignment, task snapshots, task ownership/status/evidence and completion tracking; document, asset and access-provisioning integrations remain open.

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
**Implementation status:** Built Not Tested — restricted permission-gated, effective-dated compensation records; approval and policy-controlled compensation changes remain open.
**Implementation status:** Built Not Tested — restricted permission-gated, effective-dated compensation records; approval and policy-controlled compensation changes remain open.

### ASAA-PAY-002 — Prepare payroll inputs
**Priority:** P2  
As an authorized payroll operator, I want approved attendance, leave, overtime, compensation and deduction inputs assembled for payroll review.
**Implementation status:** Built Not Tested — payroll periods, draft runs, employee payroll-entry records and arithmetic reconciliation validation; source integrations, policy calculations, reconciliation workflow, approvals and payment execution remain open.
**Implementation status:** Built Not Tested — payroll periods, draft runs and employee payroll-entry records; source integrations, calculations, reconciliation, approval and payment execution remain open.

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
**Implementation status:** Built Not Tested — customer-linked invoice creation, version-checked draft editing and issue API on branch `new`; configurable approval, contract/order/milestone linkage remain open.

### ASAA-FIN-003 — Track receivables and receipts
**Priority:** P1  
As an authorized finance user, I want to track amounts due, receipts, overdue balances and reconciliation status.
**Implementation status:** Built Not Tested — receipt recording, initial and later unapplied-balance allocation, partial settlement and outstanding-balance API on branch `new`; bank reconciliation, receipt reversal and refund workflows remain open.

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


---

# Gap-closure backlog — additional stories required for the full ASAA objective

This section records capabilities found missing, too broad, or insufficiently testable in the initial story map. These are additive requirements; they do not claim that the capabilities are implemented. Priorities are provisional and must be validated against the actual launch operating model.

## Epic O — Company lifecycle, governance and policy control

### ASAA-GAP-001 — Manage pre-incorporation and company establishment lifecycle
**Priority:** P0  
As the founder/owner, I want ASAA to distinguish preparation, establishment, active operation, restructuring and closure states so that records and workflows match the company's actual legal and operational status.
- Support a pre-incorporation workspace without falsely representing the company as legally established.
- Record confirmed legal entities, registrations, jurisdictions, effective dates and responsible owners when available.
- Gate jurisdiction-dependent payroll, tax, invoicing and statutory workflows until applicability is confirmed.
- Preserve the transition history and evidence when the company becomes formally established.

### ASAA-GAP-002 — Maintain a decision, delegation and authority register
**Priority:** P0  
As the owner, I want strategic decisions, delegated authority, limits, expiry and revocation recorded so that authority is explicit and reviewable.
- Record decision owner, approver, scope, rationale, effective date, expiry/review date and linked evidence.
- Distinguish delegation from permanent role assignment.
- Prevent expired or revoked delegations from authorizing actions.
- Support emergency/break-glass access with justification and post-event review.

### ASAA-GAP-003 — Govern policy lifecycle and exceptions
**Priority:** P0  
As a policy owner, I want policies to be drafted, reviewed, approved, published, acknowledged, superseded and retired through controlled workflows.
- Policies support versions, effective dates, applicable populations, owners and mandatory review dates.
- Exceptions require scope, rationale, approver, expiry and review.
- A transaction uses the policy version effective at the relevant event date.
- Historical decisions remain linked to the policy version applied.

### ASAA-GAP-004 — Configure legal entities, business units and inter-entity boundaries
**Priority:** P1  
As the owner, I want legal entities and operating units represented independently so that future subsidiaries, brands or business lines can be managed without confusing legal ownership.
- Support one or more entities only when confirmed and activated.
- Separate legal entity, brand, business unit, department and location concepts.
- Scope contracts, invoices, employees, assets and financial records to the correct entity.
- Prevent cross-entity access and reporting leakage unless explicitly authorized.

## Epic P — Complete workforce and people operations

### ASAA-GAP-005 — Manage workforce planning and recruitment end to end
**Priority:** P2  
As a workforce owner, I want approved headcount plans, requisitions, candidates, interview feedback, offers and hiring outcomes linked together.
- Track approved positions, vacancies, budgets and hiring owners.
- Restrict candidate personal data and interview feedback.
- Record offer approvals and candidate consent/retention rules.
- Convert an accepted candidate into an onboarding record without duplicating identity data.

### ASAA-GAP-006 — Manage performance, goals and development
**Priority:** P2  
As a manager and employee, I want goals, review cycles, feedback, development plans and outcomes recorded fairly.
- Support configurable review cycles and role-appropriate access.
- Employees can view permitted feedback and submit responses.
- Separate performance evidence from attendance or raw activity counts.
- Preserve review history and correction/appeal processes.

### ASAA-GAP-007 — Manage learning, skills and certifications
**Priority:** P2  
As a workforce manager, I want skills, training, learning plans and certification expiry tracked so that capability and compliance needs are visible.
- Link skills and qualifications to people and positions.
- Track training assignment, completion evidence and expiry.
- Restrict sensitive assessment information.
- Support organization-wide and department-specific competency frameworks.

### ASAA-GAP-008 — Manage employee lifecycle cases and confidential relations
**Priority:** P1  
As an authorized HR professional, I want confidential employee cases, grievances, accommodations and disciplinary workflows handled with restricted access.
- Case access is limited to explicitly assigned roles.
- Conflicts of interest can require reassignment.
- Record actions, evidence, decisions, employee responses and review history.
- Retention and deletion follow approved policy and applicable law.

### ASAA-GAP-009 — Manage workforce expenses, advances and benefits end to end
**Priority:** P1  
As an employee and finance reviewer, I want claims, advances, benefits, receipts, approvals, settlement and accounting references connected.
- Prevent duplicate claims and enforce configurable limits and evidence rules.
- Separate submission, approval and payment authority.
- Show claim status and settlement history to the claimant.
- Keep payroll and accounting treatment configurable and jurisdiction-dependent.

### ASAA-GAP-010 — Manage workforce availability across all work patterns
**Priority:** P1  
As an operations manager, I want office, remote, hybrid, field, travel, on-call and flexible work schedules represented.
- Policies define allowed capture and approval methods for each work pattern.
- Support time zones, overnight shifts, breaks, holidays and cross-midnight attendance.
- Offline/device submissions are reconciled with original event time and received time.
- Avoid covert or disproportionate location/device surveillance.

## Epic Q — End-to-end work, product and service delivery

### ASAA-GAP-011 — Manage enterprise work intake and prioritization
**Priority:** P1  
As a department owner, I want requests and work items submitted, categorized, assessed, prioritized, assigned and tracked across departments.
- Support configurable request types, forms, queues, service targets and ownership.
- Link requests to projects, products, customers, incidents or internal operations.
- Capture acceptance, rejection, deferral and escalation reasons.
- Provide requester-visible status without exposing restricted internal notes.

### ASAA-GAP-012 — Manage end-to-end product and service lifecycle
**Priority:** P1  
As a product/service owner, I want discovery, approval, design, build/procure, validation, launch, maintenance and retirement governed.
- Define lifecycle stages, owners, entry/exit criteria and required evidence.
- Link products/services to requirements, costs, pricing, customers, support and risks.
- Record versioning, changes, end-of-life and customer impact.
- Support physical, digital, professional and operational offerings without assuming one sector.

### ASAA-GAP-013 — Manage customer success and support cases
**Priority:** P1  
As a customer operations owner, I want customer queries, complaints, incidents, service cases, SLAs and resolutions managed.
- Support channels, categories, priority, ownership, escalation and response/resolution targets.
- Link cases to customers, contracts, products, services and known incidents.
- Restrict customer data and internal notes by role.
- Capture customer communication, resolution evidence and feedback.

### ASAA-GAP-014 — Manage marketing, campaigns and partner channels
**Priority:** P2  
As a marketing owner, I want campaigns, content, budgets, channels, approvals, partners and outcomes tracked.
- Link campaigns to products/services, audiences, leads and approved budgets.
- Track consent and communication preferences.
- Record campaign spend and measurable outcomes with source definitions.
- Support partner/referral ownership and attribution.

### ASAA-GAP-015 — Manage order fulfilment and recurring commercial commitments
**Priority:** P1  
As a commercial/operations owner, I want accepted quotations to become orders, subscriptions or service commitments with fulfilment and renewal tracking.
- Link quotation, approval, customer acceptance, order, delivery and invoice records.
- Support one-time and recurring commitments, amendments, pauses and cancellations.
- Track fulfilment status, entitlements, renewals and service obligations.
- Reconcile commercial changes with billing and customer records.

## Epic R — Full financial control and commercial accounting

### ASAA-GAP-016 — Maintain a governed financial ledger and periods
**Priority:** P1  
As an authorized finance owner, I want a configurable chart of accounts, journals, accounting periods and traceable postings.
- Journal entries balance and reference source business events.
- Closed periods require controlled reopening and audit.
- Corrections use reversals/adjustments rather than silent edits.
- Accounting policy and statutory treatment remain configurable pending jurisdiction confirmation.

### ASAA-GAP-017 — Reconcile bank, cash and payment records
**Priority:** P1  
As a finance user, I want bank/cash transactions matched to invoices, receipts, expenses and payments.
- Support manual statements and approved provider imports.
- Identify unmatched, duplicate, partial and reversed transactions.
- Reconciliation has preparer/reviewer separation where configured.
- No payment initiation without explicit provider, permission and approval setup.

### ASAA-GAP-018 — Govern tax, billing rules and invoice compliance
**Priority:** P1  
As a finance owner, I want tax treatments, invoice sequences, credit/debit notes and required invoice fields configured by legal entity and jurisdiction.
- Never assume tax rates, registration status or invoice rules.
- Effective-date tax configurations and preserve the rule used for each transaction.
- Support draft, approved, issued, corrected, voided and credited states.
- Prevent issued financial documents from being silently overwritten.

### ASAA-GAP-019 — Manage financial planning, cash flow and profitability
**Priority:** P2  
As the owner/finance lead, I want forecasts, scenarios, cash runway, margins and profitability by entity, product, client and project.
- Forecasts disclose assumptions, periods, source data and confidence.
- Actuals reconcile to approved financial records.
- Permissions restrict salary, banking and commercially sensitive details.
- Distinguish forecast, estimate and confirmed actual values.

### ASAA-GAP-020 — Manage pricing governance and commercial profitability
**Priority:** P1  
As a commercial owner, I want price lists, cost basis, discount authority, taxes, currencies, validity and margin rules connected.
- Maintain versioned price lists by product/service, customer segment and effective period.
- Discount/exception approvals follow authority limits.
- Quote/invoice retains the price and terms accepted at that time.
- Cost and margin visibility is restricted to authorized roles.

## Epic S — Procurement, physical operations and assets

### ASAA-GAP-021 — Manage procure-to-pay lifecycle
**Priority:** P2  
As a procurement and finance owner, I want purchase requests, quotations, vendor selection, purchase orders, receipts, bills and settlement connected.
- Enforce budget and approval checks before commitments.
- Record vendor comparisons and conflict-of-interest declarations where required.
- Match purchase order, receipt and supplier invoice where applicable.
- Track exceptions, returns, disputes and payment status.

### ASAA-GAP-022 — Manage inventory, warehouses and stock traceability
**Priority:** P2  
As an operations owner, I want locations, warehouses, stock lots, movements, reservations and counts managed when the business handles inventory.
- Record every stock movement with source, destination, actor and reason.
- Support configurable units, serial/lot tracking and expiry where relevant.
- Reconcile physical counts and system balances with approval history.
- Keep this capability optional for businesses with no inventory.

### ASAA-GAP-023 — Manage facilities, fleet, maintenance and physical operations
**Priority:** P2  
As an operations owner, I want facilities, vehicles, equipment, inspections, work orders and maintenance schedules tracked where applicable.
- Assign custodians, locations, condition and maintenance responsibility.
- Record inspections, faults, work orders, costs and closure evidence.
- Support safety procedures and incident escalation where relevant.
- Activate only the operational domains the company actually uses.

## Epic T — Enterprise data, integration and user experience

### ASAA-GAP-024 — Govern master data and record ownership
**Priority:** P0  
As a data owner, I want authoritative ownership, identifiers, validation, duplicate handling and lifecycle rules for shared records.
- Define authoritative source and accountable steward for each master-data domain.
- Detect possible duplicate people, customers, vendors, products and assets.
- Support merge/supersession with traceable references, not destructive deletion.
- Validate cross-domain references and preserve data lineage.

### ASAA-GAP-025 — Import, migrate and reconcile existing business data
**Priority:** P1  
As an administrator, I want controlled import and migration from approved files and systems.
- Preview mapping, validation errors, duplicates and affected records before commit.
- Support dry runs, rollback or compensating actions and reconciliation totals.
- Record source, batch, operator, timestamp and import outcome.
- Enforce the same access, privacy and validation rules as manual entry.

### ASAA-GAP-026 — Provide governed APIs, events and integration operations
**Priority:** P0  
As an integration owner, I want versioned interfaces, webhooks/events and adapter lifecycle management.
- Document authentication, scopes, rate limits, versioning and deprecation.
- Support retries, idempotency, replay controls, dead-letter/error queues and reconciliation.
- Allow credentials to be rotated and integrations revoked without losing history.
- Keep external providers replaceable and ASAA authoritative for its own records.

### ASAA-GAP-027 — Support localization, multiple locations and currencies
**Priority:** P1  
As an administrator, I want configurable language, time zone, date/number formats, currencies, holidays and regional settings.
- Store timestamps unambiguously and display them in the user's permitted locale/time zone.
- Distinguish transaction currency, base/reporting currency and exchange-rate source/date.
- Support location-specific calendars and effective-dated settings.
- Do not infer legal jurisdiction from a user's display locale.

### ASAA-GAP-028 — Provide role-personalized workspaces and accessible interaction
**Priority:** P1  
As each user, I want a workspace showing relevant tasks, approvals, records and metrics for my assigned responsibilities.
- Provide role/department-aware navigation without granting additional data access.
- Support configurable dashboards, saved views and notification preferences.
- Meet accessibility expectations for keyboard use, screen readers, contrast and responsive layouts.
- Provide usable mobile experiences for field and frontline roles.

### ASAA-GAP-029 — Support resilient mobile and intermittent-connectivity workflows
**Priority:** P2  
As an authorized field/frontline user, I want approved workflows to function during limited connectivity.
- Offline actions are limited to explicitly approved data and operations.
- Synchronization detects conflicts and never silently overwrites authoritative records.
- Sensitive cached data is protected and expires/clears according to policy.
- Show pending, synced, failed and conflict states clearly.

### ASAA-GAP-030 — Govern analytics, KPI definitions and data lineage
**Priority:** P1  
As an executive or department head, I want consistent reports whose metrics can be traced to authoritative records.
- Every KPI has a definition, owner, formula, scope, period and refresh expectation.
- Show data freshness, exclusions, assumptions and confidence.
- Drill-down and exports enforce source permissions.
- Reconcile totals across domains and flag incomplete or conflicting data.

## Epic U — Security, assurance and platform lifecycle

### ASAA-GAP-031 — Manage security incidents and vulnerability remediation
**Priority:** P1  
As a security owner, I want incidents, vulnerabilities, affected assets, response actions and closure evidence managed.
- Record severity, impact, owner, timeline, containment and remediation.
- Restrict incident details and preserve evidence.
- Support escalation, notification and post-incident review.
- Link corrective actions to risks, controls and assets.

### ASAA-GAP-032 — Manage control testing, internal audit and remediation
**Priority:** P2  
As an auditor/control owner, I want controls, test plans, findings, evidence and remediation tracked.
- Map controls to policies, risks and obligations.
- Separate control owner, tester and finding approver where required.
- Track finding severity, action owner, due date and closure validation.
- Preserve audit independence and access boundaries.

### ASAA-GAP-033 — Define service levels, release/change and environment governance
**Priority:** P1  
As a platform/service owner, I want service ownership, change records, release approvals, maintenance windows and service targets governed.
- Record service owner, dependencies, support model, availability target and escalation route.
- Changes include impact, risk, approval, test evidence, rollback and post-change review.
- Distinguish development, test and production data and permissions.
- No production release is considered complete without required operational evidence.

### ASAA-GAP-034 — Test disaster recovery and business continuity
**Priority:** P0  
As the owner, I want recovery objectives, backup retention, restore drills and continuity procedures defined.
- Define approved recovery time and recovery point objectives per critical service/data class.
- Test restoration and record evidence, gaps and corrective actions.
- Document ownership, escalation, communication and manual fallback procedures.
- Verify exports and backups are protected against unauthorized access and tampering.

### ASAA-GAP-035 — Govern configuration changes and safe rollout
**Priority:** P1  
As an administrator, I want configuration changes versioned, reviewed, tested and promoted safely.
- Track who changed what, why, when and the affected workflows/roles.
- Preview impact and validate workflows before activation.
- Support rollback or compensating changes for failed configuration releases.
- Separate test configuration from active company policy.

### ASAA-GAP-036 — Manage retention, legal holds, correction and deletion
**Priority:** P0  
As a privacy/records owner, I want retention schedules, legal holds, correction and lawful deletion handled consistently.
- Apply retention by record class, purpose and confirmed jurisdiction.
- Legal holds suspend ordinary deletion and are auditable.
- Corrections preserve provenance and required history.
- Deletion is authorized, evidenced and propagated to approved processors/backups according to documented policy.

### ASAA-GAP-037 — Govern AI agents and automated actions
**Priority:** P1  
As the owner, I want each AI agent and automation to have a defined identity, scope, data access, action permissions and supervision.
- Agents receive least-privilege, revocable permissions and cannot inherit a human's unrestricted authority.
- Separate recommendation, draft, execution and approval capabilities.
- Require human approval for sensitive HR, financial, legal, security and external commitments.
- Record inputs/references, decisions, actions, approvals, outcomes and errors while minimizing sensitive data.
- Provide disablement, incident response and rollback/compensation procedures.

### ASAA-GAP-038 — Define platform ownership, support and change adoption
**Priority:** P1  
As the owner, I want each module and business process to have an accountable owner, support route and user guidance.
- Assign product/process/data owners and operational support responsibilities.
- Provide onboarding, help, release notes and policy-change communication.
- Track adoption and unresolved support issues without invasive employee surveillance.
- Review unused or duplicated capabilities and retire them safely.

## Gap-closure delivery order

1. **P0 safety and control foundation:** GAP-001 to 004, GAP-024, GAP-026, GAP-034, GAP-036, alongside existing organization, identity, workflow, audit and privacy stories.
2. **P1 daily company operations:** workforce, work intake, product/service lifecycle, customer support, order fulfilment, pricing, finance controls, integrations, localization, role workspaces and analytics.
3. **P1 operational assurance:** security incidents, service/change governance, configuration rollout, AI governance and ownership/support.
4. **P2 expansion:** recruitment depth, performance, learning, marketing, procurement, inventory, facilities, advanced finance, audit testing and offline workflows.

**Gap-closure rule:** These additions expand the target backlog. They do not mean every domain must be activated at launch. Each capability must be enabled only when its business owner, process, policy, data classification, approval authority and legal applicability are confirmed.


## Epic V — Leadership, department and employee management

The detailed management processes and responsibility boundaries are defined in `docs/MANAGEMENT_AND_WORKFORCE_OPERATING_MODEL.md`. These stories make the management model testable; they do not assert that the future company has adopted a particular appointment, policy or employment rule.

### ASAA-GAP-039 — Govern leadership appointments and reserved authority
**Priority:** P0  
As the organization owner, I want leadership roles, appointments, reserved decisions and delegations recorded so that company management authority is explicit and reviewable.
- Support Founder, Organization Owner, CEO/Managing Director and executive roles as distinct responsibilities that may be held by one person or separated.
- Record appointment owner, scope, effective date, expiry/review date, delegation and revocation.
- Identify reserved decisions and prevent actions outside a person's current authority.
- Keep legal/statutory authority distinct from internal platform permissions; do not assume legal powers.
- Leave the launch appointment arrangement pending until owner-confirmed.

### ASAA-GAP-040 — Manage department charters and management accountability
**Priority:** P0  
As the organization owner, I want every activated department to have a charter, accountable owner, services, responsibilities, objectives, controls and escalation path.
- Support planned, active, suspended, inactive and archived department states.
- Record department purpose, scope, interfaces, head/acting owner, staffing, processes, risks and service measures.
- Assign department heads, managers and team leads with effective dates and explicit authority scopes.
- Surface vacant ownership, unassigned processes, overloaded spans and unresolved cross-department dependencies.
- Preserve history when departments are merged, split, renamed or deactivated.

### ASAA-GAP-041 — Operate management planning and review cycles
**Priority:** P1  
As a company or department leader, I want configurable planning, review and escalation cycles so that strategy is translated into accountable execution.
- Link company objectives to department goals, team plans, initiatives and employee objectives.
- Support configurable leadership, department, team and employee check-ins without imposing a fixed meeting cadence.
- Record decisions, action owners, due dates, blockers, evidence and follow-up outcomes.
- Escalate overdue or high-risk matters according to approved policy.
- Dashboards show metric definitions, source, period, freshness and authorized drill-down.

### ASAA-GAP-042 — Manage employee lifecycle as an end-to-end workflow
**Priority:** P0  
As an authorized HR owner, I want recruitment/engagement, onboarding, active employment, changes, leave/status events and offboarding connected so that employee records and access remain consistent.
- Support employees and other engagement types without conflating their legal/contractual status.
- Coordinate position, department, manager, work arrangement, documents, assets, training and access requests.
- Record effective-dated changes, approvals, evidence, notifications and history.
- Trigger access review, asset reconciliation, work handover and retention steps on transfer or exit.
- Keep employment terms, checks and statutory workflows gated by confirmed policy and applicable jurisdiction.

### ASAA-GAP-043 — Govern employee goals, performance and development
**Priority:** P1  
As an employee and manager, I want disclosed role expectations, goals, regular feedback, reviews and development plans so that performance is fair, useful and evidence-based.
- Align employee goals to approved department and company objectives.
- Support employee reflection, manager assessment, evidence, discussion, response and review history.
- Use role-appropriate criteria and documented context; do not treat attendance or activity counts as standalone performance.
- Provide correction, second-review or appeal routes as defined by approved policy.
- Keep AI recommendations advisory; prohibit opaque automated hiring, ranking, discipline, compensation or termination decisions.

### ASAA-GAP-044 — Govern manager access, employee support and workplace cases
**Priority:** P0  
As an organization owner/HR owner, I want manager access and employee support cases controlled by purpose, scope and conflict rules so that employees are protected and managers receive only necessary information.
- Separate HR reporting, project supervision, approval authority and system access.
- Restrict compensation, identity, health, grievance and disciplinary records to explicitly authorized roles.
- Support confidential case teams, conflict checks, evidence, response history and approved review/appeal routes.
- Prevent a person from accessing or deciding a case where they are conflicted unless an approved independent process explicitly permits a limited role.
- Audit access, disclosure, decisions and case closure without exposing confidential content in ordinary dashboards.



---

## AP Phase 1 implementation status — 2026-11-12

The first supplier-management API slice is being implemented under `apps/ap-api`. See [AP Phase 1 Implementation](AP_PHASE_1_IMPLEMENTATION.md) for scope, technology rationale, verification evidence and remaining gates.

| Existing story | Phase 1 coverage | Build status | Verification |
|---|---|---|---|
| ASAA-OPS-001 — Manage vendors and suppliers | Supplier registration, profiles, duplicate detection, status lifecycle and controlled updates | Built (supplier foundation only) | Passed — automated API tests |
| ASAA-FIN-004 — Manage vendor bills and payables | Supplier master dependency only; bills, due dates, approvals and payments are not implemented | Not Started | Not Tested |
| ASAA-GAP-021 — Manage procure-to-pay lifecycle | Supplier master dependency only; purchasing, receipts, invoices, matching and settlement remain future slices | Not Started | Not Tested |

**Status interpretation:** Built means implementation exists; Built Not Tested means implementation exists but verification has not been completed; Passed means the stated test/verification evidence succeeded. A Passed supplier-foundation test does not mean the full vendor, payables or procure-to-pay story is complete.
