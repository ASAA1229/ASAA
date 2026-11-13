# ASAA Project Status — Authoritative Baseline

**As of:** 2026-11-13  
**Assessed branch:** `new`  
**Initial assessment head:** `3257d883382f8cf7591457f29d267f0ebd4d7d08`  
**Latest application/test commit:** `69e08b2b591cc570d0af0eb4d8121cb32989b00c`  
**Initial maturity:** 4.5/10; **current after first verified increment:** 4.6/10 (equal-weight average of 11 dimensions)  
**Release decision:** NO-GO

This is the single authoritative source for current project status, maturity scores, verified evidence and cross-cutting gap state. Other documents define requirements, architecture, test procedures, delivery processes and acceptance criteria; they must link here rather than maintain competing project-wide status summaries.

## 1. Product identity and scope

ASAA is an internal enterprise operating platform for ASAA. The current executable slice is a React/Vite web client and a FastAPI/SQLAlchemy API with PostgreSQL migrations. Implemented domain foundations include governance and organization administration, identity/authorization foundations, supplier/AP, AR, HR/employment lifecycle, onboarding/offboarding, leave, payroll, timesheets and expenses.

The full enterprise vision also includes commercial, project/product, service delivery, operations, legal/compliance, knowledge, integrations and analytics capabilities. These are not all implemented. Preview UI, planned requirements and code foundations must not be reported as complete operational workflows.

## 2. Status vocabulary

Use only the following capability statuses in project records:

- **PLANNED** — approved scope, implementation not begun.
- **NOT STARTED** — no implementation evidence.
- **IN DEVELOPMENT** — implementation actively changing.
- **IMPLEMENTED** — code exists; required verification is not yet complete.
- **NEEDS TESTING** — implementation exists but required test evidence is missing or incomplete.
- **TEST FAILED** — an identified test failed and remains unresolved.
- **TEST PASSED** — identified test passed in a stated environment.
- **CI VERIFIED** — a named CI workflow passed for an exact commit.
- **DEVICE VERIFIED** — tested on a named physical device/browser combination.
- **OWNER ACCEPTANCE PENDING** — business or owner approval has not been recorded.
- **ACCEPTED** — authorized owner acceptance and required evidence are recorded.

A status must include evidence, commit/revision, environment, date and reviewer where applicable. A source file or passing CI run alone does not establish production operation or owner acceptance.

## 3. Maturity baseline

Scores are repository maturity, not the organization-wide ASAA score. They are evidence-based baseline judgements and will be rescored after each verified delivery increment.

| Dimension | Baseline | Current | Evidence / current limitation |
|---|---:|---:|---|
| Architecture and maintainability | 6.5 | 6.5 | Domain-separated API packages and shared DB/security services; central frontend composition and deeper maintainability review remain. |
| Requirements and documentation | 5.5 | 6.0 | Requirements, stories, architecture, security and operations exist; this status baseline and delivery evidence set are being established. |
| Implementation completeness | 5.5 | 5.5 | Governance, AP/AR, HR/payroll and workforce foundations exist; enterprise scope and provider integrations remain incomplete. |
| Unit, integration, API, UI and E2E testing | 6.5 | 6.8 | API suite and PostgreSQL integration passed in CI; UI/E2E and broad regression evidence are absent. |
| Security and privacy | 5.0 | 5.3 | RS256/JWKS, permission checks and MFA assurance hooks exist; provider activation, identity lifecycle, audit assurance and production review remain. |
| Performance and scalability | 4.0 | 4.0 | PostgreSQL pool settings exist; no load, concurrency or capacity results recorded. |
| Accessibility and compatibility | 3.5 | 3.5 | Responsive UI exists; no formal accessibility or device/browser evidence recorded. |
| CI/CD and DevOps | 5.5 | 5.8 | Three GitHub Actions workflows configured; security scanning, reproducible frontend install, artifact controls and deployment execution remain. |
| Deployment and infrastructure readiness | 2.5 | 2.5 | Production PostgreSQL preflight script exists; no production target or deployment evidence. |
| Monitoring, backup and disaster recovery | 2.0 | 2.0 | Requirements and operational guidance exist; live monitoring, backup and restore evidence absent. |
| Release readiness and operational support | 2.5 | 2.7 | Release gates documented; P0 controls, UAT, support ownership and operational sign-off remain. |

## 4. Verified repository baseline

### Branches and pull requests
- Default branch: `main`.
- Branches observed: `main`, `new`, `docs/organization-preservation-baseline`.
- Required ASAA branches `dev`, `fix` and `test` are not present.
- `main` and `new` are reported as unprotected by the branch metadata inspected. Required-check/ruleset configuration could not be fully inspected due GitHub integration permission limits.
- `new` is 408 commits ahead of `main` in GitHub compare output. Review history and scope before any merge.
- PR #1 is open from `docs/organization-preservation-baseline` to `main`; it is unrelated to the current application delivery. No merge is authorized by this status record.

### Application and data
- Frontend: React 18, Vite 6, JavaScript/JSX.
- API: Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, PyJWT.
- Database: local SQLite default; PostgreSQL 16 integration workflow; 15 migration revisions documented in the development guide.
- API tests are present under `apps/ap-api/tests`, including security, authorization, people, AP/AR, governance and PostgreSQL integration.
- No frontend test/lint scripts or frontend test suite are declared in the root `package.json`.
- No package lockfile was present in the root listing inspected; frontend CI uses `npm install`, not `npm ci`.

### CI evidence
- API quality: [run 43411431405](https://github.com/ASAA1229/ASAA/actions/runs/43411431405), **CI VERIFIED**, commit `ba87df7fdb967adf80d00b7b4771a823708b7582`.
- PostgreSQL integration: [run 43411431368](https://github.com/ASAA1229/ASAA/actions/runs/43411431368), **CI VERIFIED**, same commit. PostgreSQL 16 service started; all migrations applied; API suite passed; downgrade/re-upgrade passed.
- The latest branch head is a later documentation-only commit. These application CI runs do not validate production infrastructure.
- Web CI passed at [run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233), commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c`; npm install, 4 regression tests and Vite build all succeeded.
- No verified Jenkins agent execution, Nexus publishing/retrieval, production deployment, monitoring stack or restore exercise is recorded.

## 5. Critical gap register

| ID | Priority | Status | Current state and evidence | Required outcome / acceptance | Dependencies | Verification |
|---|---|---|---|---|---|---|
| ASAA-001 | P0 | NEEDS TESTING | PostgreSQL 16 integration passes in CI; production preflight exists but is not run against production. | Provision secured PostgreSQL; separate migration/runtime roles; TLS verification; preflight passes; capacity and migration rehearsal evidence. | Hosting, network, TLS and credentials. | Run production preflight and attach redacted output; inspect role grants and migration revision. |
| ASAA-002 | P0 | OWNER ACCEPTANCE PENDING | OIDC Authorization Code + PKCE and API RS256/JWKS validation code exist; no provider/tenant activation evidence. | Approve provider, tenant, issuer, audience, client, redirects, MFA policy, key rotation and session/logout behavior. | Owner/provider decision and tenant administration. | Provider sandbox and production configuration tests; sign-in/logout/expiry/MFA scenarios. |
| ASAA-003 | P0 | NOT STARTED | Role/assignment governance records exist; provider-side provisioning and deprovisioning are not integrated. | Reliable joiner/mover/leaver sync, revocation, retries, reconciliation and failure alerts. | ASAA-002; authoritative employee/access mapping. | Integration tests against provider sandbox and lifecycle reconciliation report. |
| ASAA-004 | P0 | NEEDS TESTING | Server-side permission dependencies, organization-scoped queries and application audit events exist; production isolation/tamper resistance not proven. | Verify tenant/record/field isolation, payroll restrictions, SoD, audit-write failure behavior and privileged access controls. | Approved role matrix, data classification and policy. | Negative API/security tests, DB privilege review and independent security review. |
| ASAA-005 | P0 | NOT STARTED | Operations document defines backup/recovery requirements; no actual backup/restore evidence. | Approved RPO/RTO/retention; encrypted automated backups; alerts; isolated restore and integrity verification. | Hosting/storage, owner-approved recovery objectives. | Timed restore exercise and evidence record. |
| ASAA-006 | P0 | OWNER ACCEPTANCE PENDING | Workflows and UI foundations exist; policy and business UAT are not accepted. | Approve organization/authority, HR/leave, payroll, procurement and finance rules; complete first-release UAT. | Named business owners and policy decisions. | Scripted UAT, signed outcomes and defect disposition. |
| ASAA-007 | P1 | NOT STARTED | API tests exist; no UI/E2E suite or accessibility evidence found. | Launch-workflow UI/E2E regression, keyboard/screen-reader and supported-browser/device tests. | Stable launch scope and test environment. | Automated reports and manual accessibility/device records. |
| ASAA-008 | P1 | NEEDS TESTING | Four Node.js identity transport-policy tests and Vite build now pass in web CI; no lockfile, frontend lint suite or dedicated recurring dependency/security scan. | Deterministic dependency installation, lockfile, broader UI/E2E tests, lint and dependency/security scanning. | Dependency review and approved npm lock strategy. | Clean CI install, lockfile consistency, UI/E2E reports and scan results. |
| ASAA-009 | P1 | NOT STARTED | PostgreSQL pool settings exist; no measured performance results. | Define budgets and validate load, concurrency, pool saturation and capacity. | Target infrastructure and workload profile. | Reproducible load-test report and remediation evidence. |
| ASAA-010 | P1 | NOT STARTED | GitHub Actions validate code; no deployment workflow or infrastructure evidence found. | Approved environment promotion, approvals, smoke tests and rollback/forward recovery. | Hosting and release ownership. | Non-production deployment rehearsal with rollback evidence. |
| ASAA-011 | P1 | NOT STARTED | Operations requirements documented; no live observability/backup service evidence. | Centralized redacted logs, metrics, traces, alert routing, incident runbooks and backup monitoring. | Hosting/monitoring provider and operational owners. | Injected-failure alert tests and operational review. |
| ASAA-012 | P1 | NEEDS TESTING | Only main/new/docs branch observed; main/new reported unprotected; new is 408 commits ahead of main. | Establish five-branch standard and review/status gates without rewriting history or merging unapproved work. | Owner/repo administration permission. | Branch inventory, protection/ruleset inspection and PR workflow test. |

## 6. Current release decision

**NO-GO for production.** P0 database provisioning, real provider activation, identity lifecycle, security assurance, recovery and business acceptance are not closed. P1 workflows must be accepted in scope or explicitly disabled/excluded before launch.

A successful PostgreSQL CI run proves only that the tested migration/API behavior worked against the disposable CI database at the recorded commit. It does not prove production TLS, least privilege, capacity, backup, restore, monitoring or UAT.

## 7. Verified closure increments\n\n### ASAA-013 — Enforce HTTPS for OIDC JWKS retrieval\n**Status:** CI VERIFIED. The OIDC browser client now applies the secure-endpoint policy to the JWKS URI as well as authorization and token endpoints. Four Node.js tests passed (HTTPS, localhost development exception, remote HTTP rejection and non-HTTP scheme rejection), and the Vite production build passed in [web CI run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233) at commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c`. This does not close provider activation or end-to-end SSO/MFA acceptance.\n\n## 8. Delivery update protocol

After each increment:
1. Record exact branch and commit.
2. Record files and behavior changed.
3. Record test command/workflow, environment and result.
4. Update the relevant gap status and evidence.
5. Re-score only dimensions materially affected by verified evidence.
6. Record regressions, limitations and owner dependencies.
7. Re-evaluate release gates.

Do not change this baseline silently. Preserve prior dated assessment records when superseded.
