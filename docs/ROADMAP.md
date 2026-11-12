# ASAA Enterprise Project Integration Platform — Initial Roadmap

This roadmap is a planning proposal, not a committed schedule. Priorities and sequencing must be confirmed after the actual project scope and directory are reviewed.

**Non-negotiable boundary:** All existing ASAA organization projects retain their own repositories, branches, specifications, directory structures and workflows. The platform analyzes and coordinates; it does not alter those project assets.

## Stage 0 — Confirm the real project baseline
- Identify the actual project directory and existing assets.
- Confirm business purpose, target users and workflows.
- Capture original stakeholder requests.
- Confirm repository access and data restrictions.
- Validate the initial user stories and POC acceptance criteria.

**Exit:** Project owner approves the baseline.

## Stage 1 — Read-only discovery foundation
- Workspace and project registry.
- Git provider authorization.
- Repository metadata and branch discovery.
- Validation/reporting of the five default branch names (`main`, `dev`, `new`, `fix`, `test`) for each connected repository.
- Directory and file inventory.
- Documentation selection and references.

**Exit:** A reviewer can reproduce the repository inventory and trace it to a revision.

## Stage 2 — Requirements and evidence
- Requirement register.
- Acceptance criteria.
- Evidence and finding records.
- Assumptions, unknowns and decisions.
- Review and approval workflow.

**Exit:** Stakeholder requirements and repository observations are distinguishable and traceable.

## Stage 3 — Project intelligence and reporting
- Project summary.
- Branch comparison.
- Requirement-to-evidence mapping.
- Gap and risk report.
- Basic architecture/dependency register.

**Exit:** A reviewer can identify known scope, evidence, gaps and unresolved questions.


## Stage 3A — Organization command center foundation (US-028 to US-032)

Detailed design: [Foundation Implementation Blueprint](FOUNDATION_IMPLEMENTATION_BLUEPRINT.md).

- Build the organization portfolio dashboard and project drill-down.
- Implement project lifecycle stages, governed transitions and milestones.
- Implement evidence-backed health dimensions with explicit unknown/stale states.
- Implement organization and project-level role-based access control.
- Implement the organization risk/blocker register with cross-project impact links.
- Validate project isolation, audit history, lifecycle rules and evidence-based rollups.

**Exit:** The first command-center milestone passes its security, functional and evidence-traceability acceptance tests. This stage does not authorize Git writes, CI/CD execution or deployment operations.

## Stage 4 — MVP enhancements
- Incremental repository analysis.
- Search and indexing improvements.
- Additional Git providers if required.
- Dependency visualization.
- Export and reporting formats.
- Role and audit refinements.

**Exit:** MVP acceptance criteria are approved and validated.

## Stage 5 — Controlled intelligence and ecosystem integration
- AI-assisted summaries and suggestions.
- Human approval of AI-generated findings.
- API integration with ASAA Templates Platform.
- Optional project-management or CI/CD metadata integrations.
- Explicitly authorized automation, if separately approved.

**Exit:** Integrations have defined contracts, permissions, audit and rollback controls.

## Release gates

No stage should advance solely because code exists. Each stage requires:
- Approved scope.
- Test evidence.
- Security/privacy review.
- Updated documentation.
- Known limitations and open risks.
- Project-owner acceptance.


## Organization-wide invariant for every stage

Every stage must preserve project independence. ASAA may provide a shared organization-level view, but each registered project keeps its own repository/repositories, branches, directory structure, specifications, requirements, technology choices, access controls and delivery lifecycle.

The roadmap must apply the ASAA default branch-name baseline `main`, `dev`, `new`, `fix`, and `test` to every project, and report gaps without automatic branch creation. It must not introduce a universal directory layout, technology stack, specification or identical merge/release workflow. Discovery is per project; cross-project relationships are explicit links only.

### Additional Stage 0 exit checks

- Confirm how projects are grouped under the ASAA organization.
- Confirm project owners and project-level access boundaries.
- Confirm that repositories can be associated with one or more projects where the real model requires it.
- Confirm that specifications and requirements are versioned and scoped to the correct project.
- Confirm the preservation/no-write policy for connected repositories.


## Enterprise operating platform expansion

The roadmap above describes the original project-intelligence foundation. It is now a capability within the broader ASAA Enterprise Operating Platform. The authoritative organization-wide target scope and delivery model are defined in [Enterprise Operating Model](ENTERPRISE_OPERATING_MODEL.md).

The enterprise roadmap must be refined into department/domain epics after organization discovery. Its initial dependency order is:

1. Organization structure, identity, roles, permissions and approval authority.
2. Shared workflow, audit, documents, notifications and integration foundations.
3. Workforce operations: employee lifecycle, attendance, leave, shifts, work logs and timesheets.
4. Project, product, engineering, testing, release and service delivery operations.
5. Customer, sales, pricing, contracts, invoicing and finance.
6. Procurement, vendors, assets, inventory, legal, compliance, risk and security.
7. Executive reporting, cross-domain analytics and governed AI/automation.

This sequence is a planning baseline, not authorization to choose a technology stack or encode unconfirmed HR, payroll, tax, accounting or legal policies. Each capability requires validated stories, owners, access rules, acceptance criteria and test evidence before implementation.
