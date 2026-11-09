# ASAA Organization Project Preservation Policy

**Applies to:** Every project and repository managed under the ASAA1229 GitHub organization  
**Owner:** ASAA  
**Status:** Baseline policy for the initial Enterprise Project Integration Platform POC

## 1. Purpose

The ASAA Enterprise Project Integration Platform provides a unified view of independent projects. It does not take ownership of their source repositories, specifications or development processes.

## 2. Assets that remain project-owned

Each project retains control over:

- Repository names, URLs, visibility and ownership.
- Repository boundaries and repository-to-project relationships.
- Branch names, branch policies, protections and contents.
- Project-specific requirements, POC documents, specifications and approved decisions.
- Directory structures, technology choices and architecture.
- Release, review, testing and deployment workflows.
- Project-specific access permissions and governance.

The platform must not impose a common repository layout, branch naming convention, technology stack, specification format or release process across projects.

## 3. Permitted platform activities

Subject to authorization and provider permissions, the platform may:

- Discover organization repositories and repository metadata.
- Read branch names, revision identifiers and directory trees.
- Read selected documentation and source files.
- Compare branches and revisions.
- Record project metadata and stakeholder-confirmed scope.
- Link findings to exact repository, branch, revision and path references.
- Map dependencies and integration relationships.
- Generate reports, gap lists and recommendations.
- Store its own analysis metadata, decisions and audit history.

## 4. Prohibited actions in the initial POC

The initial POC must not:

- Create, rename, archive, transfer or delete existing project repositories.
- Create, rename, delete or rewrite branches in existing project repositories.
- Push commits, modify files, update specifications or open pull requests in project repositories.
- Merge or consolidate project repositories.
- Reorganize directories or impose shared folder conventions.
- Change branch protection, repository permissions or project settings.
- Trigger builds, tests, deployments or production operations.
- Mark a project requirement complete solely because a file or code implementation exists.

## 5. Change requests and future write capabilities

A recommendation from the platform is not authorization to change a project. If a future feature needs to perform a write operation:

1. The affected project and target repository/branch must be identified.
2. The proposed change and its impact must be described.
3. The affected project owner must explicitly approve it.
4. The action must follow that project's existing branch, review and release process.
5. The action must be auditable and recoverable.
6. The platform must not bypass repository protections or project governance.

Write capabilities are excluded from the initial POC and require a separate approved scope.

## 6. Evidence and traceability

Every repository-derived finding should retain, where available:

- Organization and repository identity.
- Branch name.
- Commit or revision SHA.
- File path and line range.
- Inspection timestamp.
- Evidence classification.
- Reviewer status.

Reports must distinguish stakeholder-confirmed requirements, documented statements, code observations, test-verified results, operational verification, inference, assumptions and unknowns.

## 7. Project independence

Projects may have different repository counts, branch strategies, technologies, specification formats and workflows. These differences are valid and must be represented rather than normalized away.

The platform's data model must support one project with multiple repositories and branches, and must not assume that a repository name or default branch fully defines project scope.

## 8. Acceptance checks

The preservation policy is satisfied when:

- Repository and branch discovery is read-only.
- Existing project files and specifications remain unchanged.
- Findings are stored separately from source repositories.
- Every finding can be traced to its source revision.
- No cross-project standardization or migration occurs without explicit approval.
- The POC can produce useful project understanding without writing to the projects it analyzes.
