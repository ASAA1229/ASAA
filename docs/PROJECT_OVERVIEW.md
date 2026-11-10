# ASAA Enterprise Project Integration Platform — Project Overview

## 1. Product identity

- **Company:** ASAA
- **Product name:** ASAA Enterprise Project Integration Platform
- **Repository:** `ASAA1229/ASAA`
- **Product type:** Standalone project/repository intelligence and coordination platform
- **Current stage:** Initial POC definition
- **Relationship to ASAA Templates Platform:** Separate product; future integration through defined APIs or shared services only.

## 2. Problem statement

When multiple software projects are distributed across repositories, branches, directories and documentation, it is difficult to maintain one accurate understanding of:
- What each project is intended to do.
- Which requirements are confirmed by stakeholders.
- How the project is structured.
- Which capabilities are implemented, incomplete or unverified.
- Which services, APIs, databases and external systems it depends on.
- Which decisions, risks and integration tasks remain open.

A repository inspection alone cannot establish the complete product scope. Repository evidence is useful, but it must be reconciled with the actual project directory, business requests, stakeholder decisions and operational constraints.

## 3. Organization-wide preservation boundary

The ASAA organization may contain many independent projects. Every project uses the organization-wide default branch-name set `main`, `dev`, `new`, `fix`, and `test`. Each project nevertheless retains its own branch contents, protection rules, merge flow, release process, repository/repositories, directory structure, specifications, requirements, technology choices and ownership. The platform checks and reports branch-set alignment but does not create, rename, delete or rewrite branches.

The platform may discover, read, index, compare and report on authorized project assets. It must preserve the original repository/branch identity and revision when recording evidence. It must not rename or reorganize repositories, create/delete/rename branches, merge codebases, rewrite project specifications, or alter project workflows. The five organization-wide default branch names are a shared baseline, not permission for the platform to mutate repositories. Any branch creation or other future write capability must be separately scoped, explicitly authorized by the affected project owner, and executed through that project's existing governance process.

## 4. Product vision

Provide a traceable workspace where ASAA can register projects, connect repositories, understand their real structure and requirements, map dependencies, and progressively coordinate integration and delivery.

## 5. Goals

1. Maintain a structured inventory of projects and repositories.
2. Discover branches, directories and relevant files.
3. Make documentation and source evidence searchable and traceable.
4. Capture actual business scope, user requests and acceptance criteria.
5. Distinguish confirmed facts, inferred observations, assumptions and unknowns.
6. Track implementation state without treating file presence as proof of completion.
7. Map dependencies and integration contracts across projects.
8. Generate concise project reports and actionable gap lists.
9. Preserve an audit trail of analysis and stakeholder decisions.

## 6. Non-goals for the first POC

- Automatically merging repositories or combining codebases.
- Automatically changing source code or documentation.
- Committing, pushing, creating branches or opening pull requests.
- Running builds, tests, deployments or production operations.
- Replacing GitHub, project-management tools or CI/CD systems.
- Declaring production readiness from static inspection alone.
- Assuming that all projects use one language, framework or database.
- Automatically trusting AI-generated requirements or conclusions.

These may be considered later only after explicit scope, safety controls and approval workflows are defined.

## 7. Primary users and roles

| Role | Responsibility |
|---|---|
| Workspace owner | Creates workspace, configures access and governance |
| Project owner | Defines project purpose, scope and acceptance |
| Analyst | Inspects repositories and records evidence |
| Developer/technical lead | Validates architecture, implementation and dependencies |
| Reviewer/approver | Confirms requirements, findings and decisions |
| Viewer | Reads approved project information and reports |

The exact role model is provisional and must be validated with the actual users.

## 8. Core product areas

### 7.1 Workspace and project registry
Create workspaces and projects; record owners, business purpose, status, tags and links to repositories.

### 7.2 Git provider and repository connections
Authorize access, register repositories, identify default branches, and retain connection metadata securely.

### 7.3 Repository explorer
Discover branches, commits, directory trees and files. Support scoped inspection and branch comparisons.

### 7.4 Documentation intelligence
Identify relevant documentation, extract content where supported, index it and link findings to exact file paths and revisions.

### 7.5 Project scope and requirements
Capture stakeholder requests, functional requirements, non-functional requirements, constraints, acceptance criteria and decisions.

### 7.6 Evidence and implementation tracking
Record each finding with evidence type, source, branch, revision, confidence and verification status. Track requirement status separately from code presence.

### 7.7 Architecture and dependency mapping
Represent services, APIs, databases, events, external systems, ownership and dependency direction.

### 7.8 Reports and audit
Generate project summaries, repository inventories, open questions, risks, integration maps and change history.

## 9. Key information model

The initial conceptual entities are:

- Workspace
- User and Role
- Project
- Project Request
- Requirement
- Acceptance Criterion
- Decision
- Repository Connection
- Repository
- Branch
- Commit/Revision
- Directory/File Reference
- Evidence/Finding
- Component/Service
- Dependency/Integration
- Risk/Issue
- Analysis Run
- Report
- Audit Event

Relationships and fields will be refined after actual workflows and data-retention needs are confirmed.

## 10. Evidence and status vocabulary

Every recorded statement should be classified:

- **Stakeholder-confirmed:** Explicitly confirmed by an authorized project stakeholder.
- **Documented:** Present in project documentation.
- **Code-observed:** Seen in a specific source revision.
- **Test-verified:** Supported by an identified test execution and result.
- **Operationally verified:** Confirmed in the target runtime/environment.
- **Inferred:** Derived from evidence but not confirmed.
- **Assumption:** Temporary planning assumption awaiting validation.
- **Unknown:** Not yet established.

Suggested requirement states: Proposed, Under Review, Approved, In Progress, Implemented, Test Pending, Verified, Blocked, Deferred, Rejected.

A requirement must not become Verified solely because related code or documentation exists.

## 11. Quality attributes

- Security: least-privilege access, secure credential handling and auditable actions.
- Privacy: minimize collected source content and protect sensitive project data.
- Traceability: every analysis claim links to its evidence and revision.
- Reliability: repeatable discovery and recoverable analysis.
- Extensibility: multiple Git providers and heterogeneous project stacks.
- Usability: clear distinction between confirmed and uncertain information.
- Performance: incremental analysis and scoped retrieval for large repositories.
- Portability: avoid unnecessary lock-in to one cloud or AI provider.

## 12. Open questions

1. What is the actual project directory and expected top-level folder structure?
2. Which users and teams will use the platform?
3. Which Git providers must be supported initially?
4. Are repositories private, public or both?
5. Is organization-wide discovery required, or only explicitly registered repositories?
6. Which files and directories are in scope for analysis?
7. What is the expected project/requirements approval workflow?
8. Is AI analysis required in the first POC or only deterministic indexing and reporting?
9. What data may be stored, and what must remain transient?
10. Which existing tools must be integrated?
11. What is the intended hosting and deployment environment?
12. What actions, if any, may be automated after the read-only phase?

## 13. Acceptance baseline

The initial product definition is acceptable when stakeholders confirm the actual directory, scope, users, initial workflows, repository access model, data constraints and POC acceptance criteria. Until then, technology and implementation decisions remain provisional.


## 13. ASAA organization model and project independence

The platform manages multiple independent projects under the ASAA organization. Each project retains its own:
- Project identity, business purpose, scope and stakeholders.
- Git repository or repositories.
- Branch names, branch policies and release strategy.
- Directory and file structure.
- Project-specific specifications, requirements and acceptance criteria.
- Technology stack, build system, testing strategy and deployment lifecycle.
- Access permissions, ownership and change approvals.

The platform must discover and record these characteristics per project. It must not assume that branch names, directory layouts, technology choices or specification formats are uniform across the organization.

### Mandatory preservation rules

1. A registered project is a separate domain boundary.
2. A repository may be linked to a project, but linking does not transfer ownership or modify it.
3. Branches are discovered as they exist; the platform does not rename, standardize, create, delete or merge them during the POC.
4. Project specifications remain project-specific. Organization-level guidance may define governance, but cannot silently replace a project's approved requirements.
5. Cross-project dependencies are represented as relationships between independent projects/services, not by merging their repositories.
6. Analysis records must identify the project, repository, branch and revision to which they apply.
7. A project owner must approve any future change to that project's scope or specification.
8. Read-only access is the default. Any future write capability requires a separate approved workflow, explicit authorization and audit trail.

The organization dashboard may aggregate status and dependencies, but project-level source records remain authoritative within their own boundaries.

## 14. Multi-project data hierarchy

Conceptual hierarchy:

```text
ASAA Organization
  └── Workspace / Portfolio
       ├── Project A
       │    ├── Project-specific specifications
       │    ├── Repository A1
       │    │    ├── Branches
       │    │    └── Directories and files
       │    └── Repository A2 (optional)
       ├── Project B
       │    ├── Project-specific specifications
       │    └── Repository B1
       └── Project C
            └── Repository C1
```

This is a logical relationship model, not a requirement that every project have exactly one repository or that all projects use the same structure.

See [Organization Model](ORGANIZATION_MODEL.md).
