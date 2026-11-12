# ASAA — Enterprise Project Integration Platform

**Status:** Initial documentation and proof of concept (POC)  
**Stage:** Planning baseline — implementation not started  
**Owner:** ASAA

## Purpose

ASAA Enterprise Project Integration Platform is a standalone application intended to help ASAA understand, organize, analyze and coordinate multiple software projects and their repositories.

The initial product should establish a reliable view of each project's actual purpose, scope, directory structure, branches, documentation, requirements, implementation evidence and dependencies. It should not assume that repository names, README files or previously collected reference information are the definitive project specification.

## Product boundary

This is a separate product and Git repository. It is not a module inside the ASAA Templates Platform. A future API-based integration may allow both products to exchange project metadata or reuse capabilities without coupling their release cycles.

## Initial POC

1. Register an organization/workspace and projects.
2. Connect an authorized Git provider account or repository.
3. Discover repositories, default branches, branches and directory trees.
4. Select documentation and source areas for analysis.
5. Capture project purpose, scope, requirements and constraints with source references.
6. Record repository observations separately from confirmed requirements.
7. Map project dependencies and integration points manually in the first iteration.
8. Produce a project/repository summary and an explicit list of unknowns and verification tasks.

## Organization-wide preservation rule

Every project under ASAA1229 remains independently owned, with its own repositories, specifications, requirements, directory structure, technology choices and project-specific workflow. The organization-wide default branch set for every project is **`main`, `dev`, `new`, `fix`, and `test`**. These are common branch-name defaults; they do not make project code, requirements, folder layouts or project-specific workflows identical. The platform records whether each repository has the expected branches but does not create, rename, delete or modify branches. Any branch rollout or exception is handled through the affected project's approved process.

## Guiding principles

- Treat actual project scope and user requests as the source of truth.
- Keep reference observations separate from approved project requirements.
- Preserve traceability from findings to repository, branch, path and revision.
- Read-only repository access by default.
- No code changes, commits, pushes, merges, deployments or test execution in the initial POC.
- Do not infer that documented or present code is working or production-ready.
- Make uncertain, missing and unverified information visible.
- Support multiple projects and Git repositories without assuming a particular organization structure.

## Documentation

- [Project overview](docs/PROJECT_OVERVIEW.md)
- [Organization preservation policy](docs/ORGANIZATION_PRESERVATION_POLICY.md)
- [Proof of concept](docs/POC.md)
- [User stories](docs/USER_STORIES.md)
- [Initial roadmap](docs/ROADMAP.md)
- [Command center foundation implementation blueprint](docs/FOUNDATION_IMPLEMENTATION_BLUEPRINT.md)

## Decisions intentionally left open

The production technology stack, hosting model, database, exact Git provider integration, AI provider, access model, detailed UI/UX and automation permissions must be decided after the real project directory, scope, workflows and constraints are collected.

## Current status

This repository contains planning documentation only. No application code, integrations, tests or deployment configuration are included in this initial baseline.


## Organization and project-preservation model

ASAA is the organization-level workspace. Each software project remains independent, with its own repository/repositories, directory structure, specifications, requirements, technology choices, ownership and delivery lifecycle. The shared branch-name baseline is `main`, `dev`, `new`, `fix`, and `test`; project-specific branch protections, merge flows and additional branches remain governed by each project's approved workflow.

The platform provides a centralized view without combining codebases or imposing a universal project structure. It reports missing default branches but does not create or change them.

See [Organization Model](docs/ORGANIZATION_MODEL.md) and [Branch Standard](docs/BRANCH_STANDARD.md) for the mandatory rules.
