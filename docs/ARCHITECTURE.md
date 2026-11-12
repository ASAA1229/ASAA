# ASAA Architecture

**Product:** ASAA Enterprise Operating Platform  
**Architecture status:** Foundational logical architecture; owner validation and iterative implementation required  
**Technology policy:** Technology-stack independent across the platform

## 1. Architectural intent

ASAA is an integrated internal operating platform for the organization being established. It connects business domains while preserving clear ownership of records, policies, permissions and lifecycle decisions. It is not a monolithic HR, ERP, CRM or project-management product, and it is not intended to impose a uniform stack on every domain.

The architecture must work for a small early-stage organization and scale as capabilities, people, business units and locations are activated. A single person may hold multiple responsibilities. The department catalogue describes possible organizational capabilities; it is not an instruction to activate every department or create an artificial hierarchy.

## 2. Core architecture decisions

1. **Domain-oriented modularity.** Business capabilities are separated into bounded domains with explicit ownership and interfaces. Modules may share platform services without sharing uncontrolled business logic.
2. **Technology autonomy.** Each module selects its language, framework, database, hosting and tools according to its needs. Reuse is encouraged where it reduces complexity, not mandated.
3. **Shared platform capabilities.** Identity, authorization, organization hierarchy, reference data, workflow/approval, audit, documents, notifications, integration registry and reporting are cross-cutting capabilities.
4. **Authoritative records.** Each domain defines its system of record, data owner, lifecycle, retention, access rules and integration contract. Cross-domain links reference authoritative records instead of creating conflicting copies.
5. **Configurable policies.** Departments, roles, permissions, approval matrices, limits, workflows, statuses, currencies and locations are configurable and versioned. Unknown company/legal policies are not hard-coded as facts.
6. **Human governance.** Sensitive HR, financial, legal, security and high-impact automated actions require authorized human decisions; maker-checker controls apply where appropriate.
7. **Replaceable integrations.** Provider-specific APIs and formats are isolated behind adapters. Integrations are scoped, revocable, observable, reconcilable and auditable.
8. **Evidence-based state.** A capability is not declared verified because code or documentation exists. Build, test and runtime evidence remain distinct.
9. **Progressive delivery.** Establish secure foundations and deliver coherent vertical slices rather than implementing every capability simultaneously.

## 3. Logical platform domains

### Governance and organization
Organization/legal-entity lifecycle, business units, divisions, departments, teams, locations, leadership, delegated authority, policies, decisions, risk, compliance and internal controls.

### People and workforce
Person directory, employees and non-employees, recruitment, onboarding, employment lifecycle, attendance, shifts, leave, timesheets, compensation, payroll, performance, learning, employee relations and offboarding.

### Projects, products and technology
Portfolio, programs, projects, product lifecycle, requirements, roadmaps, repositories, engineering, QA, CI/CD, environments, releases, support and technical knowledge.

### Services and operations
Service catalogue, client delivery, work orders, scheduling, SLAs, support, procurement, suppliers, inventory, assets, facilities, travel and operational procedures.

### Commercial and customer
Leads, accounts, contacts, CRM, proposals, quotations, contracts, orders, subscriptions, customer onboarding, communications and feedback.

### Finance
Budgets, estimates, invoices, receivables, payables, receipts, expenses, reimbursements, cash flow, accounting and payroll accounting. Tax, statutory and accounting behavior must be configured only after jurisdiction and policy are confirmed.

### Legal, security and compliance
Contracts, obligations, legal registers, privacy, consent, identity lifecycle, security incidents, access reviews, retention, audit, risk and regulatory evidence.

### Knowledge, collaboration and intelligence
Documents, knowledge base, communication, calendars, meetings, action items, search, reporting, KPIs, forecasting, AI assistance and controlled automation.

These are capability boundaries, not a claim that every domain is implemented or active.

## 4. Organization and access model

The conceptual hierarchy may include:

`Organization → legal entity/business unit → division → department → team → role/position → person`

Not every layer must exist at launch. Matrix reporting and multiple team/role membership must be supported where approved.

Keep these concepts distinct:
- Job title vs application role.
- Reporting manager vs approval authority.
- Organization membership vs access to sensitive records.
- Department membership vs project/customer/financial record scope.
- Read permission vs approval, administration or execution permission.
- Employment status vs account/device access status.

Access is scoped by organization and, where needed, business unit, department, project, customer, record classification and action. A role template is not itself proof that a user should receive every permission associated with a broad job title.

## 5. Cross-domain record relationships

Business events connect through explicit references. Examples:
- A person links to employment, team, leave, attendance, compensation and access records.
- A client contract links to opportunities, projects, milestones, invoices, receipts and support obligations.
- A product links to requirements, engineering, QA, releases, pricing and support.
- A project links to people allocation, timesheets, budgets, procurement, risks and deliverables.
- An invoice links to a customer, contract/order, project/service, tax treatment and accounting entry.

Each relationship records source and target, owning domain, type, provenance, access rules and verification state. Integrations must address idempotency, duplicate delivery, retries, reconciliation, partial failure, rate limits and stale data.

## 6. Current API implementation architecture

The current API is a modular service located at `apps/ap-api`:

- Python 3.11+, FastAPI and Pydantic v2.
- SQLAlchemy 2 for persistence and Alembic for schema migrations.
- PostgreSQL driver via psycopg 3; SQLite is used for local development and automated tests.
- PyJWT RS256 verification for upstream identity tokens.
- pytest and HTTPX for automated tests.

The finance package (`asaa_ap`) contains shared database, configuration, principal/security dependencies, audit model, supplier/AP and AR routers/services. The people package (`asaa_people`) contains HR, onboarding/offboarding and payroll models, schemas, routes and workflow/lifecycle logic. The routers reuse the existing database, organization-scoped principal, permission dependency and audit event table.

This Python stack is a module-level implementation choice, not a platform-wide technology mandate. Future modules may use other appropriate technologies and integrate through documented APIs/events or other explicit contracts.

## 7. Data and workflow rules

- Organization identity is derived from a verified principal; callers cannot choose another organization scope in request payloads.
- Sensitive mutations require explicit permissions and validated state transitions.
- Version checks protect mutable records against lost updates where implemented.
- Important decisions record actor, time, outcome, reason and target.
- Maker-checker separation prevents a maker from approving their own protected action where enforced.
- Effective-dated records preserve historical context and reject invalid overlap where implemented.
- Documents and external assets use references/adapters; private binary storage is not assumed to exist.
- Currency, tax, leave, payroll, approval and retention policies remain configurable inputs pending owner/legal validation.

## 8. Project and repository independence

ASAA may provide portfolio visibility over independent projects. Each project remains authoritative for its own identity, purpose, owner, requirements, repository/repositories, directory structure, technology stack, tests, release process and approvals.

The organization-wide default branch names are `main`, `dev`, `new`, `fix` and `test`. This is a naming baseline only. Additional branches are allowed; protections, merge flows, CI/CD triggers, release rules and contents remain project-specific. The presence of a branch name does not prove quality or production readiness.

For read-only project/repository intelligence, record exact repository, branch, revision and path provenance. Do not create, rename, delete or modify repositories, branches, files or specifications; do not run repository scripts or trigger builds/deployments. Any future write capability requires a separately approved feature, scoped authorization, owner approval, audit and recovery plan.

## 9. Integration and event principles

- Use documented, versioned contracts and stable identifiers.
- Keep provider-specific behavior in adapters.
- Request minimum scopes; support revocation and credential rotation.
- Preserve source, timestamp, transformation, sync state and confidence for external data.
- Design safe retries and idempotency keys.
- Detect duplicate and out-of-order events.
- Provide reconciliation for financially or operationally important records.
- Expose connection health and data freshness; stale data must never appear current.
- Prefer exportable formats and avoid unnecessary provider lock-in.

## 10. Quality attributes

Security and privacy; traceability; reliability and recoverability; extensibility; interoperability; accessibility and usability; performance through scoped queries and incremental processing; portability; maintainability; testability; observability; and data lifecycle governance.

## 11. Architecture decisions still requiring owner confirmation

Legal entity and jurisdictions; actual active departments and reporting model; identity provider and MFA; role-to-permission mappings; approval authority and thresholds; data classification and retention; document/notification providers; hosting and PostgreSQL service; backup/recovery objectives; integration priorities; UI framework and user experience; and production support ownership.
