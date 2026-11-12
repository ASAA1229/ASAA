# ASAA Organization Command Center — Foundation Implementation Blueprint

**Target stories:** US-028, US-029, US-030, US-031 and US-032  
**Target branch:** `new`  
**Status:** Implementation design — awaiting technology and operating-model approval  
**Scope:** Organization portfolio command center foundation  
**Repository safety:** This product repository may be changed on the approved working branch. Connected ASAA project repositories remain read-only and independently governed.

## 1. Objective

Deliver the first usable ASAA command center: a trusted organization-level view of independent projects, their lifecycle, evidence-backed health, access boundaries, risks and blockers.

The command center is an intelligence and coordination layer. It must not merge projects, normalize their technology stacks, rewrite project requirements, or mutate connected repositories.

## 2. Delivery boundary

### Included in this foundation milestone

- Organization/workspace portfolio overview.
- Project registration and project detail views needed to support portfolio records.
- Configurable project lifecycle and auditable stage transitions.
- Milestone tracking with owners, dates, status and completion evidence.
- Evidence-backed project health dimensions and transparent rollups.
- Organization and project-level roles and access enforcement.
- Organization-wide risk/blocker register with project-level ownership and drill-down.
- Audit history for privileged actions and material record changes.
- Seed/demo data clearly labelled as demonstration data, never presented as real ASAA project facts.

### Explicitly excluded

- GitHub synchronization or repository writes.
- Jenkins/CI/CD integration or pipeline execution.
- Build, test, deployment or production environment operations.
- Automated project status changes based on repository file presence.
- AI-generated decisions or autonomous remediation.
- Cross-project requirement copying or repository consolidation.
- Production hosting, identity-provider integration and secret-store selection until approved.

## 3. Core product principles

1. **Project independence:** project records, owners, scope, requirements and lifecycle remain separately governed.
2. **Evidence before claims:** every material health/status claim has a source, timestamp and verification state.
3. **Unknown is not success:** missing or stale evidence is shown as unknown/stale, never silently treated as healthy.
4. **No fabricated percentages:** progress percentages are shown only when derived from an explicit, approved denominator and defined calculation.
5. **Least privilege:** organization membership does not automatically grant access to every project.
6. **Human-controlled transitions:** stage changes and risk closure require authorized actions and audit events.
7. **Traceable aggregation:** every organization metric can be drilled down to its project-level source records.
8. **Safe defaults:** no connected-repository write access is introduced by this milestone.

## 4. Domain model

The following is a logical model, not a database-vendor-specific schema. Physical types, indexes and migrations are selected after the technology decision.

### Organization and access

| Entity | Purpose | Key relationships |
|---|---|---|
| Organization | ASAA tenant boundary | Has workspaces, users and policies |
| Workspace | Optional grouping boundary for a portfolio | Belongs to organization; contains projects |
| User | Authenticated human identity | Has organization and project memberships |
| OrganizationMembership | Organization-level role and state | Links user to organization |
| ProjectMembership | Project-specific role and state | Links user to project |
| Role / Permission | Defines allowed actions | Assigned through memberships |
| AuditEvent | Immutable record of material actions | References actor, scope, action and target |

### Portfolio and delivery

| Entity | Purpose | Key relationships |
|---|---|---|
| Project | Independent project identity, purpose, owner and status | Belongs to organization/workspace |
| LifecycleDefinition | Configurable lifecycle stages and transition rules | Scoped to organization or project |
| ProjectStageHistory | Records each stage transition | Belongs to project; records actor and evidence |
| Milestone | Dated delivery objective | Belongs to project; has owner and evidence |
| Requirement | Approved project scope item | Belongs to one project unless explicitly shared |
| VerificationEvidence | Supports implementation/test/operational claims | Links to requirement, milestone or health dimension |
| HealthAssessment | Snapshot of evidence-backed project health | Belongs to project and records calculation version |

### Risk and blockers

| Entity | Purpose | Key relationships |
|---|---|---|
| RiskItem | Risk, blocker, incident or unresolved decision | Has one owning project and optional affected projects |
| RiskProjectLink | Associates a risk with multiple affected projects | Does not merge project records |
| RiskMitigation | Mitigation action, owner and due date | Belongs to risk |
| RiskStatusHistory | Status/severity/ownership history | Belongs to risk; creates audit events |

### Important relationship rules

- A project belongs to one ASAA organization and may belong to a workspace.
- A project can have multiple owners and members through project memberships; the accountable primary owner is explicitly identified.
- A milestone, requirement, stage history and project health assessment always retain project scope.
- A cross-project risk has one accountable owning project and explicit links to other affected projects.
- Organization-level standards and project-specific policies are separate records.
- Shared requirements or lifecycle definitions require explicit adoption/approval; they are not implicitly copied.
- Repository, branch and CI/CD entities are later integrations and must link to projects without becoming project identity.

## 5. Lifecycle model — US-029

### Default stage vocabulary

1. Planning
2. Design
3. Development
4. Testing
5. Release / Published
6. Maintenance
7. Archived

A project may define additional stages or more detailed transitions. The default vocabulary is a baseline, not a forced identical release process.

### Transition behavior

Every transition records:

- Project and previous/new stage.
- Actor and timestamp.
- Reason and linked evidence.
- Entry/exit checklist result.
- Approval decision where policy requires it.

A transition is rejected when required checks are incomplete or the actor lacks permission. Historical transitions are append-only; corrections create a new event rather than rewriting history.

### Release-readiness guard

A project cannot be labelled Released/Published or production-ready merely because source code, a README, a branch or a deployment record exists. The project must satisfy its own approved release criteria and retain verification evidence. If no criteria have been defined, readiness is Unknown and the missing decision is surfaced.

## 6. Evidence-backed health — US-030

### Health dimensions

- Scope and requirements
- Implementation
- Testing and quality
- Security
- Delivery and release
- Operational readiness

Dimensions may be marked Not Applicable only with a recorded rationale and authorized decision.

### Evidence states

- Stakeholder-confirmed
- Documented
- Code-observed
- Implemented (owner/reviewer-confirmed)
- Test-verified
- Operationally verified
- Blocked
- Deferred
- Inferred
- Assumed
- Unknown
- Stale

These states are not interchangeable. In particular, code-observed is not test-verified, and test-verified is not operationally verified.

### Health calculation rules

- Show a state per dimension before attempting an overall rollup.
- Every state links to supporting or missing evidence, its source, revision/run where applicable, verifier and timestamp.
- Stale evidence is visibly stale and cannot support a current healthy state without revalidation.
- Missing evidence produces Unknown, not Passed.
- Blocked and Deferred remain explicit states and are not counted as completed.
- Not Applicable is excluded from a denominator only after approval and rationale.
- If a numeric score is introduced later, its formula, weights, denominator, freshness window and calculation version must be visible and approved.
- Do not display a single overall percentage when the underlying data does not support a meaningful calculation.
- Manual owner overrides require rationale, actor, timestamp and expiry/review date; the underlying evidence-based assessment remains visible.

### Portfolio rollup

The portfolio view aggregates project states, not raw incomparable percentages. It should show counts by state and dimension, projects with stale evidence, and the projects contributing to each count. Users can drill down to the project assessment and evidence.

## 7. Access model — US-031

### Initial role catalogue

| Role | Organization scope | Project scope |
|---|---|---|
| Organization Owner | Full organization administration and policy ownership | Access only as explicitly granted or under a documented break-glass policy |
| Organization Admin | Manage organization users, workspace settings and integrations | No automatic access to restricted project content |
| Project Owner | No organization-wide administration | Manage project records, members, lifecycle, milestones and risks |
| Contributor | No organization-wide administration | Create/update permitted project work records |
| Reviewer / Approver | No organization-wide administration | Review and approve assigned records/transitions |
| Read-only Viewer | View only explicitly granted organization-level summaries | Read only granted project data |

### Authorization requirements

- Deny by default; check permission on every server-side read and write.
- Organization membership does not imply project membership.
- Project membership is independently assignable and revocable.
- Privileged operations require explicit permissions, not UI-only hiding.
- Cross-project views must filter every underlying record by the caller's effective access.
- Sensitive fields and integration secrets are excluded from ordinary project views and audit payloads.
- Membership grants, revocations, role changes, approvals and denied privileged actions are auditable.
- Production identity provider, MFA and account lifecycle integration remain deployment/security decisions to approve.

## 8. Risk and blocker register — US-032

### Risk record fields

- Unique ID and type: Risk, Blocker, Incident or Decision.
- Title and detailed description.
- Accountable owning project.
- Affected projects (zero or more).
- Severity and likelihood/impact where applicable.
- Status: Open, Investigating, Mitigating, Accepted, Resolved or Closed.
- Owner, created date, target date and next action.
- Related requirements, milestones, dependencies or environments.
- Evidence, mitigation actions and decision rationale.
- Last-updated timestamp and full status history.

### Register behavior

- Highlight critical/high-severity, overdue, unowned and stale items.
- Filter by project, owner, severity, type and status.
- Support one risk affecting multiple projects without duplicating its authoritative record.
- Require a resolution note and evidence/reference before marking resolved where applicable.
- Risk acceptance requires an authorized approver, rationale and review/expiry date.
- Project owners can manage risks in their projects; organization-level risk visibility follows access permissions.
- Organization summaries show counts and affected project links, not private details to unauthorized viewers.

## 9. Application surfaces

### Organization command center

- Portfolio totals by lifecycle stage and status.
- Project list with purpose, accountable owner, lifecycle stage, health confidence and last verified update.
- Risks/blockers summary and overdue milestones.
- Stale or missing evidence/integration indicators.
- Filters and drill-down into authorized projects.
- Clear indication of demo data, unknown data and last refresh time.

### Project overview

- Project purpose, scope, owner and lifecycle.
- Milestones and next actions.
- Health dimensions with evidence status.
- Open risks and blockers.
- Recent decisions and audit activity.
- Links to project-specific requirements and evidence.

### Lifecycle and milestones

- Stage timeline and transition history.
- Entry/exit checklist.
- Milestone list/calendar with owner, target date and evidence.

### Risk register

- Filterable organization/project risk list.
- Risk detail, affected projects, mitigation actions, owner and history.

### Access administration

- Organization members and roles.
- Project members and roles.
- Effective-access preview and audit history.

### Audit history

- Actor, action, target, scope, timestamp, outcome and correlation identifier.
- Never store credentials, tokens or unnecessary sensitive payloads in audit records.

## 10. Logical API responsibilities

Route names are illustrative and should be adapted to the approved API conventions.

| Capability | Example operations |
|---|---|
| Portfolio | `GET /api/portfolio/summary`, `GET /api/projects` |
| Projects | `GET /api/projects/:projectId`, `POST /api/projects`, `PATCH /api/projects/:projectId` |
| Lifecycle | `GET /api/projects/:projectId/lifecycle`, `POST /api/projects/:projectId/transitions` |
| Milestones | `GET/POST /api/projects/:projectId/milestones`, `PATCH /api/milestones/:id` |
| Health | `GET /api/projects/:projectId/health`, `GET /api/portfolio/health` |
| Evidence | `GET/POST /api/projects/:projectId/evidence` |
| Risks | `GET/POST /api/risks`, `GET/PATCH /api/risks/:riskId` |
| Membership | `GET/POST /api/projects/:projectId/members`, organization membership administration |
| Audit | `GET /api/audit-events` with enforced scope filters |

All writes require server-side authorization, validation, audit events and concurrency-safe updates. Pagination, filtering, stable IDs, consistent error responses and API versioning are required. No API in this milestone writes to connected Git repositories.

## 11. Non-functional requirements

- **Security:** least privilege, secure sessions, CSRF protection where applicable, input validation, output encoding, rate limiting and secure secret handling.
- **Privacy:** collect only necessary user/project data; enforce project-level isolation in queries, exports and logs.
- **Auditability:** append-only history for approvals, role changes, lifecycle transitions and risk decisions.
- **Reliability:** transactional updates for state changes; idempotent handling where retries are possible.
- **Performance:** paginated portfolio queries, indexed organization/project/status/owner fields and bounded dashboard aggregation.
- **Accessibility:** keyboard-operable controls, semantic structure, visible focus and sufficient contrast.
- **Usability:** show unknown/stale states explicitly and avoid misleading green/success indicators.
- **Maintainability:** modular boundaries for portfolio, projects, lifecycle, evidence, access and risks.
- **Observability:** structured application logs, request correlation IDs and health endpoints without leaking sensitive data.

## 12. Verification plan

### US-028 — Portfolio

- Register multiple projects with different scopes and owners; verify all appear independently.
- Verify filters and drill-down return only authorized records.
- Verify totals reconcile with project-level records.
- Verify stale/missing data is labelled, not shown as healthy.

### US-029 — Lifecycle

- Verify default stages and project-specific extensions.
- Reject transitions when entry criteria or permission are missing.
- Verify every accepted transition creates history and audit events.
- Verify release readiness cannot be inferred from code or branch existence.

### US-030 — Health

- Verify each health dimension can be Unknown, Blocked, Deferred, stale or verified as appropriate.
- Verify code-observed evidence cannot satisfy test verification.
- Verify stale evidence changes the displayed confidence/state.
- Verify unsupported numeric completion is not shown.
- Verify rollups link to the exact contributing assessments.

### US-031 — Access

- Test each role against every read/write capability.
- Verify organization membership alone does not grant project access.
- Verify project A members cannot access project B restricted records.
- Verify revocation takes effect and is audited.
- Verify unauthorized API calls are denied even when directly invoked.

### US-032 — Risks

- Create a risk owned by one project and affecting multiple projects.
- Verify one authoritative risk record appears in permitted project/organization views.
- Verify critical, overdue and unowned filters.
- Verify resolution/acceptance requires rationale and appropriate permission.
- Verify unauthorized users cannot see restricted risk details.

### Cross-cutting

- Unit tests for lifecycle rules, health calculations and authorization policies.
- API integration tests for tenant/project isolation and audit creation.
- UI tests for portfolio filtering, drill-down and accessible workflows.
- Security tests for authorization bypass, IDOR, injection, session handling and sensitive-data leakage.
- Migration/backup/recovery tests once persistence and hosting are selected.

## 13. Delivery sequence

### Foundation A — Confirm decisions and architecture
- Approve application stack, persistence, hosting and identity approach.
- Confirm organization/workspace semantics and role authority.
- Approve lifecycle transition governance and health calculation policy.
- Finalize data model and API contracts.

**Exit:** Decisions recorded; implementation-ready architecture approved.

### Foundation B — Secure application skeleton
- Create application structure and environment configuration.
- Establish authentication/session boundary and server-side authorization framework.
- Add persistence, migrations, validation, structured errors and audit foundation.
- Add automated test and quality gates.

**Exit:** Secure, tested application shell with no cross-project data leakage.

### Foundation C — Portfolio and project foundation (US-028)
- Project registry and organization portfolio dashboard.
- Filters, project drill-down and explicit data freshness.
- Demo fixtures clearly marked as demo.

**Exit:** Portfolio data reconciles with project records and respects access rules.

### Foundation D — Lifecycle and milestones (US-029)
- Configurable stages, transitions, milestone records and evidence links.
- Entry/exit validation and immutable stage history.

**Exit:** Invalid transitions are blocked and valid transitions are auditable.

### Foundation E — Health and progress (US-030)
- Evidence model and dimension assessments.
- Transparent health rollups, freshness and unknown states.

**Exit:** Health output is reproducible from source evidence and never invents completion.

### Foundation F — Roles and risk register (US-031/032)
- Organization/project membership management and authorization tests.
- Risk/blocker register, mitigation and cross-project impact links.

**Exit:** Access isolation and risk workflows pass their acceptance tests.

### Foundation G — POC validation and review
- Run the complete verification plan.
- Document limitations, test evidence, security review and unresolved decisions.
- Obtain project-owner acceptance before advancing to engineering integrations.

## 14. Decisions required before application coding

The existing POC and README explicitly leave the production stack and operating model open. The following choices must be approved before Foundation B:

1. **Application stack:** frontend framework, backend framework/runtime and language.
2. **Persistence:** relational database and migration/ORM approach.
3. **Hosting:** local-only POC, self-hosted internal deployment, or cloud deployment.
4. **Authentication:** local accounts for the POC or an existing identity provider; MFA expectations.
5. **Organization/workspace semantics:** whether ASAA has one organization with multiple workspaces, or whether workspaces are the top-level user-managed boundary.
6. **Role authority:** who can grant organization admin and project owner roles; whether organization admins can view restricted project details.
7. **Lifecycle governance:** whether the default stage list and transition approvals are acceptable as written.
8. **Health governance:** approve evidence states and whether any numeric scoring is desired; default is state-based, no invented percentage.

Until these decisions are approved, keep implementation at the design and validation level. Do not silently select infrastructure, create production accounts, request broad provider permissions or introduce write-capable integrations.

## 15. Relationship to existing documentation

- `docs/USER_STORIES.md`: US-028 through US-032 are the acceptance source for this milestone.
- `docs/ORGANIZATION_MODEL.md`: project independence and organization/project boundaries remain mandatory.
- `docs/ORGANIZATION_PRESERVATION_POLICY.md`: connected project repositories remain read-only.
- `docs/BRANCH_STANDARD.md`: the five branch names remain an organization baseline; the command center only reports branch compliance until Git integration is separately approved.
- `docs/POC.md`: this blueprint expands the command-center foundation without removing the original read-only POC constraints.
- `docs/ROADMAP.md`: this is a detailed implementation design for the first organization-wide gap-closure milestone, not evidence that any feature is already implemented.

## 16. Current implementation status

| Story | Design status | Application status |
|---|---|---|
| US-028 Portfolio command center | Specified in this blueprint | Not started |
| US-029 Lifecycle and milestones | Specified in this blueprint | Not started |
| US-030 Evidence-backed health | Specified in this blueprint | Not started |
| US-031 Role-based access | Specified in this blueprint | Not started |
| US-032 Risk and blocker register | Specified in this blueprint | Not started |

No application code, database, identity integration or deployment configuration is claimed as complete by this document.
