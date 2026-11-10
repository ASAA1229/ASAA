# ASAA Organization-Wide Default Branch Standard

**Status:** Organization baseline  
**Applies to:** Every project and repository under the ASAA1229 organization  
**Default branch names:** `main`, `dev`, `new`, `fix`, `test`

## 1. Policy

Every project under ASAA is expected to use the same five default branch names:

| Branch | Standard intent |
|---|---|
| `main` | Stable, approved production baseline |
| `dev` | Shared development/integration baseline |
| `new` | New feature or capability development |
| `fix` | Defect correction and maintenance work |
| `test` | Testing, validation and quality assurance |

These descriptions establish the intended default purpose of each branch. The exact merge direction, protection settings, release gates, deployment triggers and approval requirements must be confirmed and configured through the applicable project governance; this document does not silently impose one identical workflow on every project.

## 2. What is standardized

- The five branch names above are the organization-wide defaults.
- New project/repository setup should include these five branches as part of its approved bootstrap checklist.
- Existing project repositories should be assessed against the five-name baseline.
- Organization-level reports should show branch presence/missing status per repository and project.
- Additional branches are permitted when a project needs them.

## 3. What remains project-specific

The following remain governed by each project's approved requirements and workflow:

- Branch protection and required reviewers.
- Merge direction and pull-request strategy.
- Release and deployment rules.
- CI/CD triggers and validation gates.
- Additional feature, hotfix, release or experiment branches.
- Branch-specific ownership and permissions.
- Code, documentation and configuration contained in each branch.

The common branch names do not make projects share code, specifications, directory structures, technology stacks or release schedules.

## 4. Rollout and safety

- The POC only reads and reports branch presence; it does not create, rename, delete, merge or modify branches.
- A missing default branch is reported as a project-owner action item.
- Any rollout to an existing repository must be approved and carried out under that project's established change-control process.
- The platform must never infer that a branch is safe to create from its name alone.
- Branch-name presence is not proof of branch protection, code quality, testing or production readiness.

## 5. Acceptance checks

1. Every registered project is associated with one or more repositories.
2. Every repository can be checked for all five default branch names.
3. Missing branches are visible at repository and project level.
4. Additional branches do not cause a compliance failure.
5. No repository mutation occurs during discovery.
6. Reports retain repository, branch and revision provenance.
7. Project-specific protections and merge flows remain distinct and are not inferred from names.

## 6. Open decisions

Before implementation beyond the read-only POC, ASAA must confirm:
- Whether the five branches are required in every repository or at project level where multiple repositories have different roles.
- Whether branch names are case-sensitive and whether aliases are prohibited.
- Exact merge flow between `new`, `fix`, `dev`, `test` and `main`.
- Required protection rules and approval counts for each branch.
- How existing repositories will be brought into compliance.
