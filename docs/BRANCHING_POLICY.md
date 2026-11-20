# ASAA Git, Branching, Ignore and Repository Governance Standard

**Effective:** 2026-11-16  
**Applies to:** ASAA, JARVIS, Templates and Portfolio repositories in the ASAA1229 organization.  
**Canonical policy owner:** ASAA organization repository.

This document defines the standard Git workflow, branch purposes, pull-request routing, promotion mechanisms, commit and release practices, repository hygiene, and ignore rules. Repository-specific build and deployment instructions remain in each repository.

## 1. Core Git principles

- Git history is the audit trail. Do not rewrite shared history.
- Keep changes small, reviewable, attributable and reversible.
- Never commit credentials, private keys, tokens, real environment files, personal data, generated secrets or machine-specific configuration.
- Do not commit generated dependencies, caches, temporary files, test output or local build artifacts unless a project explicitly requires a generated artifact to be versioned.
- Do not assume that a file is ignored merely because it appears in a local `.gitignore`; verify tracked status with Git.
- Never bypass required reviews, status checks or repository protections.
- A clean working tree is required before switching branches, rebasing, merging or starting unrelated work. Preserve and report pre-existing user changes; never discard them.

## 2. Required branch set

Every active ASAA1229 project repository must maintain these five standard branches:

| Branch | Purpose | Rules |
|---|---|---|
| `main` | Production/release baseline | Protected. No direct work commits. Receives approved release promotion only. |
| `dev` | Shared integration baseline | Protected. Receives approved integration promotion only. |
| `new` | Primary development and feature-integration branch | Default target for normal feature, maintenance and project work PRs. |
| `fix` | Isolated defect and urgent correction work | Work is validated here as appropriate; shipping changes are submitted to `new` unless an explicitly approved emergency procedure says otherwise. |
| `test` | Test engineering, QA, experiments and verification | Test-only work stays here; product changes intended for delivery must be proposed to `new`. |

The five branch names are a required organization standard. Their existence must be checked in each repository; this document does not itself create missing branches.

## 3. Standard branch workflow

### 3.1 Normal feature or maintenance work

1. Fetch and inspect the latest remote state.
2. Start from the latest appropriate base, normally `origin/new`.
3. Use `new` for direct integration work only when authorized by the project owner; otherwise use a descriptive short-lived feature branch based on `new`.
4. Open a pull request with **base = `new`**.
5. Complete code review, required CI checks, tests, security checks and documentation updates.
6. Merge only after required approvals and checks pass.
7. Delete the short-lived feature branch after merge when it is no longer needed.

### 3.2 Defect fixes

1. Reproduce and record the defect.
2. Use `fix` or a descriptive fix branch based on the appropriate current work baseline.
3. Add regression coverage where practical.
4. Submit the delivery PR to `new`.
5. Emergency production fixes require explicit owner approval, a documented reason, regression verification and a follow-up synchronization into `dev` and `new`. Never silently bypass the normal controls.

### 3.3 Testing work

- Use `test` for QA experiments, test harnesses, fixtures and verification-only changes.
- Keep test data synthetic or appropriately anonymized.
- If a test discovers a product defect, create a fix and route it through the normal fix-to-`new` workflow.
- Do not merge experimental test-only changes into production branches without review.

### 3.4 Promotion to integration and production

1. **`new` → `dev`:** only through an explicit promotion PR, review, required CI checks and owner approval.
2. **`dev` → `main`:** only through an explicit release PR, release verification, required CI checks and owner approval.
3. Record the release version/tag, change summary, migration impact, rollback approach and deployment evidence.
4. After a release or emergency fix, reconcile the affected branches so that approved fixes are not lost.

Routine feature PRs must not target `dev` or `main` directly.

## 4. Branch naming and commit conventions

- Prefer descriptive short-lived names such as `feature/<short-topic>`, `bugfix/<short-topic>`, `hotfix/<short-topic>`, `test/<short-topic>` and `docs/<short-topic>`.
- Use lowercase names and hyphens; avoid spaces and vague names.
- Use clear commit messages. Recommended prefixes: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `build:`, `ci:`, `chore:` and `security:`.
- One commit should represent a coherent change. Do not mix unrelated project changes.
- Do not commit generated files, secrets or unrelated formatting churn.
- Do not amend or rebase commits already shared with others unless an explicitly approved, coordinated operation requires it.

## 5. Pull-request requirements

Every PR must state:
- What changed and why.
- Which issue, requirement, epic or task it addresses.
- Impacted applications, services, APIs, schemas, data and integrations.
- Tests executed and their actual results.
- Security, privacy, compatibility and migration considerations.
- Configuration or environment changes.
- Risks, rollback considerations and known limitations.
- Documentation updated.

PR checks should include the repository's applicable formatting, lint, type-check, unit, integration, API, browser/E2E, security, build and artifact validation. A skipped or unavailable check must be explicitly identified; it must not be reported as passing.

## 6. Required repository protections

Configure GitHub rulesets or branch protection for `main` and `dev` at minimum:
- Require pull requests before merging.
- Require at least one independent review, with stricter review requirements where risk warrants.
- Require the relevant CI/status checks.
- Require branches to be up to date where appropriate.
- Dismiss stale approvals when new commits materially change the reviewed code.
- Restrict force pushes and branch deletion.
- Restrict bypass to explicitly authorized administrators and document any bypass.
- Apply equivalent controls to tags/releases where supported.

**Verification status:** this document defines the required controls; it does not prove that GitHub rulesets or branch protections are currently configured. Inspect actual repository settings and record evidence before declaring compliance.

## 7. Synchronization and conflict handling

- Fetch before starting work and before promotion.
- Integrate the latest target branch using the repository's approved merge/rebase strategy.
- Resolve conflicts deliberately; inspect the resulting diff and rerun affected tests.
- Never use force push to resolve ordinary divergence.
- If a push is rejected, fetch and inspect the remote state before retrying.
- Do not overwrite another contributor's commits or uncommitted work.
- Keep long-running branches synchronized regularly and avoid accumulating large, unrelated changes.

## 8. Git ignore and generated-file policy

Each repository must maintain a root `.gitignore` and may add narrower nested ignore files where necessary. Ignore patterns should be specific, documented and reviewed. Do not use broad patterns that hide source code, migrations, required configuration, fixtures or test assets.

### 8.1 Organization-wide ignored categories

The following categories must be excluded from Git unless a documented project exception applies:

| Category | Common patterns / examples |
|---|---|
| Node dependencies | `node_modules/` |
| Build output | `dist/`, `build/`, `dist-ssr/`, framework-generated output such as `.output/` |
| Python bytecode | `__pycache__/`, `*.py[cod]`, `*$py.class` |
| Python environments | `.venv/`, `venv/`, `env/` |
| Python/test caches | `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/` |
| Test output | `coverage/`, `test-results/`, `playwright-report/` |
| Environment secrets | `.env`, `.env.*`, local secret files; allow only safe example templates such as `!.env.example` |
| Credentials and private keys | `*.pem`, `*.key`, secret/credential directories |
| Logs and temporary files | `*.log`, temporary scratch directories and local runtime state |
| Local databases and backups | `*.db`, `*.sqlite3`, local backup directories, when they contain generated/local data |
| OS/editor files | `.DS_Store`, `Thumbs.db`, local IDE state such as `.idea/` and machine-specific files |
| Generated archives and reports | Build archives, checksums, local release manifests, generated SBOMs and temporary verification output, where not an explicitly published release artifact |

The exact patterns vary by technology and repository. Preserve safe sample configuration, required fixtures, source-controlled test assets, migration files and intentionally versioned release metadata.

### 8.2 npm package-lock policy

Per the repository owner's instruction effective 2026-11-16:
- Remove the root `package-lock.json` from each of the four project repositories.
- Add `package-lock.json` to each root `.gitignore`.
- Do not recreate or commit these files unless the owner changes this policy.

**Build impact:** `npm ci` requires a package lockfile. Pipelines and developer instructions for repositories following this policy must use a compatible install process such as `npm install`, and must not claim lockfile-reproducible dependency installation. Dependency ranges should be reviewed and versions constrained appropriately. Reconsider this policy if deterministic npm dependency resolution becomes a release requirement.

This instruction applies to `package-lock.json`; it does not automatically authorize ignoring every ecosystem's lockfiles. Review `pnpm-lock.yaml`, `yarn.lock`, Gradle dependency metadata and other lockfiles according to the relevant project's reproducibility and build requirements.

### 8.3 .gitignore mechanics

- `.gitignore` prevents untracked matching files from being added by normal Git workflows.
- It does **not** stop tracking a file that is already committed.
- To stop tracking an already tracked generated file while preserving the local copy, use `git rm --cached <path>`, then commit the index change.
- Check the effective rule with `git check-ignore -v <path>`.
- Check whether a file is already tracked with `git ls-files <path>`.
- Review `git status --short` and the staged diff before committing.
- Do not delete a required local environment file simply because it is ignored.
- Never add secrets to Git, even temporarily; removing a secret in a later commit does not remove it from history. Rotate exposed credentials and follow the incident process.

## 9. Dependency and package management

- Commit source manifests and dependency configuration required to install and build the project.
- Follow the repository's explicitly approved lockfile policy.
- Do not silently switch package managers or regenerate dependency metadata.
- Review dependency changes for compatibility, known vulnerabilities, licensing and supply-chain risk.
- CI must use the install command compatible with the committed dependency metadata and must fail clearly when required inputs are absent.
- Do not treat a successful dependency installation as proof that dependencies are reproducible or secure.

## 10. CI, Jenkins and build mechanisms

- Jenkins is the shared CI automation server; the configured Jenkins endpoint uses port `8443`. Obtain hostname, protocol and credentials from approved configuration or Jenkins credentials management; never hard-code secrets.
- Each project pipeline must check out the intended repository and branch, install dependencies, run applicable quality/security/test stages, build, publish test reports and archive approved artifacts.
- CI jobs must identify the commit SHA and branch being built.
- Keep project jobs and shared Jenkins configuration separate; do not overwrite another project's job or shared credentials.
- Use least-privilege credentials and isolated workspaces. Never execute untrusted repository code on a privileged shared agent without an appropriate isolation boundary.
- A green pipeline is evidence only for the stages it actually ran. Record skipped stages and external dependencies honestly.
- CI configuration changes require review and must not trigger production deployment unless separately authorized.

## 11. Tags, releases and deployment

- Use annotated, versioned tags for formal releases, following the project's versioning convention.
- A release must identify its source commit, change summary, test evidence, artifacts, known issues and rollback procedure.
- Do not tag an unverified or unreviewed commit as a production release.
- Deployment is a separate authorized operation; a successful build does not authorize deployment.
- Keep release artifacts immutable and retain provenance, checksums and relevant build metadata.

## 12. Branch lifecycle and repository maintenance

- Keep the five required standard branches available.
- Delete short-lived branches only after their PR is merged or formally abandoned and no dependent work remains.
- Do not delete `main`, `dev`, `new`, `fix` or `test` as routine cleanup.
- Periodically review stale branches, open PRs, ignored-file drift, dependency health, branch protections and CI reliability.
- Record exceptions with owner, rationale, affected repositories, approval and expiry/review date.

## 13. Compliance and evidence

For each repository, maintain evidence for:
- Presence and purpose of the five standard branches.
- Default branch and branch protection/ruleset configuration.
- PR base-branch routing and required checks.
- Root and nested ignore rules.
- Absence of prohibited generated files and secrets from the Git index.
- CI/Jenkins job configuration, tested commit SHA and build results.
- Release tags, artifacts and approvals.

Mark an item **verified** only after inspecting the actual repository or platform configuration. A written policy is not evidence of enforcement.

## 14. Change control

Changes to this organization-wide policy require explicit owner approval and an update to this document. Repository-specific exceptions must be recorded here or linked from the relevant repository, with scope and rationale. The policy applies consistently to ASAA, JARVIS, Templates and Portfolio unless a formally approved exception is documented.


## Organization branch promotion policy — 2026-11-20

Required flow across ASAA1229 repositories: task/working branches (including `fix` and `test`) → `new`; only `new` → `dev`; only `dev` → `main`. Do not open direct PRs from working branches to `dev` or `main`, or from `new` directly to `main`. All five standard branches exist in the organization snapshot, but were observed without branch protection; enforcement is approved and remains pending application/verification. No merge or promotion is performed by this documentation update.
