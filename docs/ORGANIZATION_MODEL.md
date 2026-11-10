# ASAA Organization and Project Preservation Model

**Status:** Foundational product rule  
**Applies to:** Every project registered under the ASAA organization

## 1. Purpose

ASAA needs a unified way to understand and coordinate its software portfolio. A unified view must not turn independent projects into one project or force them into a common repository structure.

The platform is an organization-level intelligence and coordination layer over independent project domains.

## 2. Non-negotiable project boundaries

Each project retains its own:

- Identity, name, purpose and business scope.
- Project owner, stakeholders and approval authority.
- Repository or repositories.
- The organization-wide default branch names `main`, `dev`, `new`, `fix`, and `test`, plus any project-specific additional branches, branch policies and release lifecycle.
- Directory structure and file organization.
- Specifications, requirements and acceptance criteria.
- Technology stack, frameworks and build tooling.
- Testing approach and deployment environments.
- Access permissions and data ownership.

These characteristics are discovered and recorded per project. The platform must not infer that one project's structure or conventions apply to another.

## 3. Organization-level responsibilities

The organization layer may:

- Register and list projects.
- Provide portfolio dashboards and consolidated reports.
- Show project owners, statuses and risks.
- Discover and index authorized repository metadata.
- Map dependencies between projects.
- Show shared services and integration relationships.
- Provide organization-level governance and audit visibility.
- Compare projects without rewriting their records.

Organization-level policies may establish minimum security, privacy and governance requirements. They must not silently rewrite approved project-specific functional requirements.

## 4. Project-level responsibilities

Each project remains authoritative for:

- Its own scope and requirements.
- Its own specifications and design decisions.
- Its own repositories and branches.
- Its own implementation and testing status.
- Its own release and deployment decisions.
- Its own project-level approvals.

A platform finding may propose a change, but only an authorized project owner/reviewer can approve it.

## 5. Repository and branch preservation

For the initial POC:

- All repository connections are read-only.
- Every project is expected to use the organization-wide default branch-name set: `main`, `dev`, `new`, `fix`, and `test`.
- The platform discovers and reports the presence or absence of these five branches for each repository.
- Missing default branches are compliance gaps for the project owner to address through the project's approved workflow; the platform does not create them.
- Project-specific additional branches, branch protections, merge flows and release policies remain supported.
- Branches are discovered and checked against the shared name baseline, not mutated.
- Directory structures are inventoried, not reorganized.
- Files are inspected, not modified.
- No commits, pushes, merges, branch creation or deletion occur.
- No repository scripts or workflows are executed.
- Every finding records the exact repository, branch, revision and path.

Any later write capability requires a separate approved feature, explicit user authorization, scoped permissions, audit logging and a recovery/rollback plan.

## 6. Specification and requirement preservation

Requirements belong to a project. They must not be copied into another project's approved scope merely because projects share a technology or integration.

For every specification, record where possible:

- Project identifier.
- Document or source location.
- Version, branch or revision.
- Owner/approver.
- Effective status.
- Change history.

Shared or reusable requirements must be explicitly marked as shared standards or templates, with the projects that adopt them identified individually.

## 7. Cross-project integration model

A dependency is a relationship, not a merger.

Examples:
- Project A consumes an API owned by Project B.
- Project C publishes an event used by Project A.
- Project B uses a shared identity service.
- Two projects use the same external provider.

Each relationship should record:
- Source project/component.
- Target project/component.
- Integration type: API, event, database, file, shared library, identity, infrastructure or external service.
- Contract or interface reference.
- Data ownership.
- Authentication/authorization expectations.
- Evidence source.
- Verification status.
- Responsible owners.

A dependency may be proposed, inferred, documented, code-observed, test-verified or operationally verified. These states must not be conflated.

## 8. Information hierarchy

```text
ASAA Organization
  └── Portfolio / Workspace
       ├── Project A
       │    ├── Scope and specifications A
       │    ├── Repository A1
       │    │    ├── Branches A
       │    │    └── Directories/files A
       │    └── Repository A2 (if applicable)
       ├── Project B
       │    ├── Scope and specifications B
       │    └── Repository B1
       └── Project C
            └── Repository C1

Cross-project dependencies are explicit links between project components.
They do not merge project records or repositories.
```

This is a conceptual model. The actual organization may have projects with multiple repositories, repositories shared by multiple project areas, or other structures. Those relationships must be captured from real requirements rather than assumed.

## 9. Required product behavior

The platform must support:
1. The five organization-wide default branch names are consistently recognized, while project-specific branch policies, merge flows and additional branches are preserved.
2. Heterogeneous directory structures.
3. Different technology stacks.
4. Different documentation and specification formats.
5. Project-level access control.
6. Project-specific approval workflows.
7. Organization-level aggregation with project-level drill-down.
8. Explicit and traceable cross-project dependencies.
9. Read-only repository discovery in the POC.
10. Clear separation of facts, assumptions, inferences and unknowns.

## 10. Acceptance tests for the preservation model

- Register two projects and verify that each is checked for `main`, `dev`, `new`, `fix`, and `test`; preserve any additional branches and do not mutate either repository.
- Register two projects with different folder layouts; both are represented accurately.
- Attach different specifications to each project; neither overwrites the other.
- Record a dependency between projects; neither project is merged.
- Generate a portfolio report; every metric can be traced to its project.
- Attempt an unauthorized project-level view; access is denied.
- Run repository discovery; no remote write operation is performed.

## 11. Change-control rule

No change to a project's scope, specification, repository, branch strategy or workflow may be applied by inference or organization-wide default. The change must be proposed, reviewed by the relevant project owner and explicitly approved. The platform records the decision and its effective version.
