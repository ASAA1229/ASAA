# ASAA DevOps and Delivery Controls

**Authoritative current state:** [Project Status](PROJECT_STATUS.md).  
**Scope:** GitHub Actions, build reproducibility, security supply chain, deployment and operational integration evidence.

## 1. Configured GitHub Actions

| Workflow | Purpose | Configured behavior | Latest evidence |
|---|---|---|---|
| `.github/workflows/people-api-ci.yml` | API quality | Python 3.12, install, compile, pytest, SQLite migration cycle | CI VERIFIED: [43411431405](https://github.com/ASAA1229/ASAA/actions/runs/43411431405), commit ba87df7 |
| `.github/workflows/postgres-integration.yml` | PostgreSQL validation | Disposable PostgreSQL 16, migrations, full API suite, downgrade/re-upgrade | CI VERIFIED: [43411431368](https://github.com/ASAA1229/ASAA/actions/runs/43411431368), commit ba87df7 |
| `.github/workflows/portal-ci.yml` | Web regression and build | Node.js 22, npm install, `npm run test:web`, Vite production build | CI VERIFIED: [43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233), commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c` |

All three workflows use read-only repository contents permissions. CI execution is not deployment.

Latest web evidence: [run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233), commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c`; npm install, the 4-test `test:web` suite and Vite production build all passed. The run reported 0 npm audit vulnerabilities for that dependency resolution, which is not a substitute for a recurring dedicated security scan.\n\n## 2. Build and dependency reproducibility

Current observed state:
- API dependencies are declared in `apps/ap-api/pyproject.toml` using version ranges.
- Frontend dependencies are declared in root `package.json` using version ranges.
- No root npm lockfile was present in the inspected branch tree.
- Web CI uses `npm install`, not `npm ci`. The web workflow now runs `npm run test:web` before the production build.
- No dependency vulnerability scan, license policy, SBOM, signed provenance or artifact checksum workflow was evidenced.

Required improvements:
1. Generate and commit the approved npm lockfile.
2. Use deterministic clean installation in CI.
3. Establish dependency update and vulnerability remediation policy.
4. Add appropriate Python and npm dependency scanning.
5. Generate an SBOM and artifact checksums; verify provenance before promotion.
6. Retain build/test artifacts with commit and workflow references.

## 3. Branch and review governance

Required ASAA branches: `main`, `dev`, `new`, `fix`, `test`.

Observed branches: `main`, `new`, `docs/organization-preservation-baseline`. Branches `dev`, `fix` and `test` were not present. `main` and `new` metadata reported unprotected. Full ruleset/required-check inspection was restricted by GitHub integration permissions.

The `new` branch is reported 408 commits ahead of `main`. Inspect the complete history and compare before proposing any merge. PR #1 is a separate open documentation PR from `docs/organization-preservation-baseline` to `main`; it is not authorization to merge the current application branch.

No force-push, branch deletion, history rewrite or merge to `main` is authorized by this document.

## 4. Jenkins and Nexus

No Jenkinsfile or Nexus publishing/retrieval configuration was found in the inspected repository tree. Jenkins is known to exist locally in the user's Windows environment, but its agent execution, credentials, job configuration and repository pipeline behavior have not been verified in this assessment. No Nexus artifact publication or retrieval is claimed.

If these tools are selected for this project, verify actual agent execution, credentials scope, artifact coordinates, checksums, retention and retrieval from the target repository before marking integration complete.

## 5. Deployment and release controls

Not evidenced in the repository:
- Infrastructure-as-code or environment provisioning.
- Staging/production deployment workflow.
- Environment-specific secret management integration.
- Approval gates and deployment identity separation.
- Health/smoke checks after deployment.
- Rollback or forward-recovery automation.
- Production release artifact retention and provenance.

Required sequence:
1. Select and approve hosting/network/environment design.
2. Provision isolated development/test/staging/production resources.
3. Use separate migration and runtime identities.
4. Build immutable artifacts and attach SBOM/checksums/provenance.
5. Require review and environment-specific approval.
6. Run migration rehearsal, deployment smoke tests and post-deploy verification.
7. Exercise rollback/forward recovery in non-production.
8. Record release commit, artifact, migration revision, approver and outcome.

## 6. Monitoring and operations

Central logs, metrics, traces, alert routing, on-call ownership, incident management and backup monitoring are requirements only until configured and tested in a real environment. See [Operations](OPERATIONS.md) and [Release Readiness](RELEASE_READINESS.md).

Do not report CI as deployment, a configured Jenkins endpoint as a working pipeline, or a configured Nexus repository as a verified artifact flow.


## 7. Changes made 2026-11-13 (configured, not yet executed on GitHub)

| Workflow | Change |
|---|---|
| `portal-ci.yml` | `npm ci` from the now-tracked `package-lock.json`; steps for `npm run lint`, `test:web`, `test:ui`, `build`; new job `web-dependency-audit` (`npm audit --audit-level=high`); path filters include `tests/**`, lockfile and tool configs. |
| `people-api-ci.yml` | New job `python-dependency-audit` (`pip-audit`); new job `local-load-and-smoke` (spawned API, 20 s load run with p95 regression budget, JSON artifact upload). |
| `release-smoke.yml` | New manual, read-only post-deploy smoke workflow taking a base URL. |

Resolved from section 2: lockfile generated and committed; deterministic clean install configured; Python and npm dependency scanning configured. Still open: dependency update/remediation policy, SBOM, artifact checksums, provenance, license policy. YAML for all four workflows parses; none of these changed definitions has a recorded GitHub run, so none is marked CI VERIFIED.

Deployment, environments, approvals and rollback remain not implemented: they require a hosting target, release owner and secrets store. Exactly what is needed is listed in [Operations](OPERATIONS.md) section 11.
