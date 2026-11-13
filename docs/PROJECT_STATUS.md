# ASAA Project Status — Authoritative Baseline

**As of:** 2026-11-13  
**Assessed branch:** `new`  
**Initial assessment head:** `3257d883382f8cf7591457f29d267f0ebd4d7d08`  
**Latest verified application commit:** `69e08b2b591cc570d0af0eb4d8121cb32989b00c`  
**Latest documentation refresh:** 2026-11-13 (engineering increment on branch `new`, commits after `fc5bba5`)  
**Initial maturity:** 4.5/10; **after first verified increment:** 4.6/10; **current after the 2026-11-13 engineering increment:** 5.4/10 (equal-weight average of 11 dimensions; local evidence only, see section 3)  
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

| Dimension | Baseline | Previous | Current | Evidence / current limitation |
|---|---:|---:|---:|---|
| Architecture and maintainability | 6.5 | 6.5 | 6.8 | Added `asaa_identity` package behind a provider contract, separate observability/hardening modules, ESLint-clean frontend with dead code removed. Central frontend composition (single large `App.jsx`) remains. |
| Requirements and documentation | 5.5 | 6.0 | 6.3 | Docs reconciled with implemented evidence; external decisions and exact configuration still needed are now enumerated (OPERATIONS section 11). |
| Implementation completeness | 5.5 | 5.5 | 6.0 | Identity lifecycle adapter + mock provider, structured logging/metrics, backup/restore tooling, smoke/load tooling added. Real provider adapters, document storage, notifications, procure-to-pay and policy engines remain absent. |
| Unit, integration, API, UI and E2E testing | 6.5 | 6.8 | 7.6 | Local: API 125 passed with PostgreSQL, 123 passed / 2 skipped without; 17 jsdom UI + axe tests; 4 Node tests; 15 negative security tests. No real-browser E2E and no CI run yet for the new commits. |
| Security and privacy | 5.0 | 5.3 | 6.2 | Route-inventory deny-all, JWT forgery/claim tests, cross-org IDOR, payroll field isolation, fail-closed audit tests, redacted logs, security headers, body limit, docs disabled in production. Provider/MFA activation, DB audit immutability and independent review remain. |
| Performance and scalability | 4.0 | 4.0 | 5.0 | Reproducible load script with measured local numbers (TESTING section 4). No budgets, target infrastructure, soak or saturation evidence. |
| Accessibility and compatibility | 3.5 | 3.5 | 5.0 | Automated axe checks found and fixed unnamed icon buttons and added dialog semantics. No contrast, screen-reader, zoom or device/browser evidence. |
| CI/CD and DevOps | 5.5 | 5.8 | 6.8 | Lockfile tracked, `npm ci`, lint, UI tests, npm audit and pip-audit jobs, smoke workflow, load job configured. YAML syntax validated only; none of the changed workflows has a recorded run yet. No deployment automation. |
| Deployment and infrastructure readiness | 2.5 | 2.5 | 3.0 | Post-deploy smoke script, production hardening (docs off, metrics gated, headers). No production target or deployment evidence. |
| Monitoring, backup and disaster recovery | 2.0 | 2.0 | 4.0 | Health/readiness, request IDs, JSON redacted logs and metrics verified locally; backup -> restore -> verify verified locally on SQLite and PostgreSQL 18. No live monitoring, alert routing, automated schedule, off-site storage or approved RPO/RTO. |
| Release readiness and operational support | 2.5 | 2.7 | 3.2 | Gate evidence is clearer; P0 external gates are unchanged. Still NO-GO. |

Scores are repository maturity judgements (not the organization-wide score). The 2026-11-13 re-score uses only evidence listed in this document; items validated locally and not yet in CI are scored conservatively.

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
- Web: `npm run test:web` (4 Node.js OIDC policy tests), `npm run test:ui` (17 Vitest/Testing Library/axe tests), `npm run lint` (ESLint flat config) and `npm run build`. `package-lock.json` is now tracked (it was previously git-ignored) and CI uses `npm ci`. No real-browser E2E suite exists.
- API: 16 Alembic revisions (0016 adds identity sync tables); new packages `asaa_identity`, `asaa_ap.observability`, `asaa_ap.hardening`; scripts `backup_restore.py`, `load_test.py`, `smoke_test.py`.

### CI evidence
- API quality: [run 43411431405](https://github.com/ASAA1229/ASAA/actions/runs/43411431405), **CI VERIFIED**, commit `ba87df7fdb967adf80d00b7b4771a823708b7582`.
- PostgreSQL integration: [run 43411431368](https://github.com/ASAA1229/ASAA/actions/runs/43411431368), **CI VERIFIED**, same commit. PostgreSQL 16 service started; all migrations applied; API suite passed; downgrade/re-upgrade passed.
- The latest branch head is a later documentation-only commit. These application CI runs do not validate production infrastructure.
- Web CI passed at [run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233), commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c`; npm install, 4 regression tests and Vite build all succeeded.
- Initial and final local verification of the 2026-11-13 increment is recorded in section 7. CI workflows changed in that increment have not yet been executed on GitHub.
- No verified Jenkins agent execution, Nexus publishing/retrieval, production deployment, monitoring stack or restore exercise is recorded.

## 5. Critical gap register

| ID | Priority | Status | Current state and evidence | Required outcome / acceptance | Dependencies | Verification |
|---|---|---|---|---|---|---|
| ASAA-001 | P0 | BLOCKED BY EXTERNAL DEPENDENCY | PostgreSQL 16 integration passed in CI (earlier commit). Locally verified on PostgreSQL 18: all 16 migrations upgrade/downgrade/re-upgrade, full API suite incl. PostgreSQL integration, pg_dump/pg_restore round trip. Production preflight script exists but has not been run against production. | Provision secured PostgreSQL; separate migration/runtime roles; TLS verification; preflight passes; capacity and migration rehearsal evidence. | Hosting, network, TLS and credentials. | Run production preflight and attach redacted output; inspect role grants and migration revision. |
| ASAA-002 | P0 | BLOCKED BY EXTERNAL DEPENDENCY | OIDC Authorization Code + PKCE and API RS256/JWKS validation code exist. Locally verified: forged (alg none, wrong key), wrong issuer/audience, expired, missing-claim and malformed-permission tokens rejected on every API route; unconfigured identity fails closed with 503; MFA acr/amr enforcement test. No provider/tenant activation. | Approve provider, tenant, issuer, audience, client, redirects, MFA policy, key rotation and session/logout behavior. | Owner/provider decision and tenant administration. | Provider sandbox and production configuration tests; sign-in/logout/expiry/MFA scenarios. |
| ASAA-003 | P0 | PARTIALLY COMPLETE | Implemented `asaa_identity`: `IdentityProvider` contract, in-memory mock with fault injection, subject links, transactional outbox, joiner/mover/leaver processing, revocation (disable + session revoke + entitlement clear), exponential backoff, dead-letter with audit/log alert, operator retry, reconciliation report with optional repair, hooks on exit completion and assignment review/revoke, `/api/v1/identity-sync` API, worker. 15 local tests pass against the mock only. No real provider adapter exists. | Reliable joiner/mover/leaver sync, revocation, retries, reconciliation and failure alerts against the real provider. | ASAA-002; authoritative employee/access mapping; provider SCIM/admin API credentials. | Integration tests against provider sandbox and lifecycle reconciliation report (not possible without a provider). |
| ASAA-004 | P0 | PARTIALLY COMPLETE | `tests/test_security_negative.py` (15 tests) passed locally: every `/api/` operation denies a zero-permission principal; token forgery/claims; cross-organization IDOR on employees, suppliers, customers, compensation, leave, audit; HR access cannot reveal compensation; maker cannot self-approve; mass assignment rejected; audit events attributable and org-scoped; mutation is rolled back when the audit write fails (fail closed, generic 500). No defects found by these tests. Production tamper resistance, DB privilege review and independent review are not done. | Verify tenant/record/field isolation, payroll restrictions, SoD, audit-write failure behavior and privileged access controls. | Approved role matrix, data classification and policy; independent reviewer. | Negative API/security tests (done locally), DB privilege review and independent security review (pending). |
| ASAA-005 | P0 | PARTIALLY COMPLETE | `scripts/backup_restore.py` (SQLite online backup API; PostgreSQL pg_dump -Fc/pg_restore; SHA-256 manifest; row-count and Alembic revision verification; optional Fernet encryption; refuses overwrite without --force; rejects passwords in URLs). 9 local tests incl. corrupted/missing-manifest/wrong-key detection and a PostgreSQL 18 round trip pass. No approved RPO/RTO/retention, no schedule, no off-site encrypted storage, no alerting, no timed restore at production scale. | Approved RPO/RTO/retention; encrypted automated backups; alerts; isolated restore and integrity verification. | Hosting/storage, owner-approved recovery objectives. | Timed restore exercise and evidence record on the real environment. |
| ASAA-006 | P0 | BLOCKED BY EXTERNAL DEPENDENCY | Workflows and UI foundations exist; policy and business UAT are not accepted. No engineering action can close this. | Approve organization/authority, HR/leave, payroll, procurement and finance rules; complete first-release UAT. | Named business owners and policy decisions. | Scripted UAT, signed outcomes and defect disposition. |
| ASAA-007 | P1 | PARTIALLY COMPLETE | 17 Vitest/Testing Library tests (sign-in, 401 handling, permission-scoped fetching, AR/AP/people views, payroll gating, create dialog, error display) plus automated axe checks on 17 launch workspaces and key dialogs passed locally. Defects found and fixed: crash with partially-permitted sessions; "API connected" after 401; unnamed icon buttons; dialog semantics. jsdom cannot evaluate contrast/layout; no real-browser E2E, screen-reader or device testing. | Launch-workflow UI/E2E regression, keyboard/screen-reader and supported-browser/device tests. | Stable launch scope, real browsers/devices, test environment. | Automated reports (done for jsdom) and manual accessibility/device records (pending). |
| ASAA-008 | P1 | COMPLETE AND VERIFIED (locally tested) | `package-lock.json` is tracked (was git-ignored); `npm ci` succeeds; ESLint flat config, `npm run lint` = 0 problems; `npm audit --audit-level=high` = 0 vulnerabilities (a vulnerable Vitest 3 dependency chain was caught by the audit and replaced by Vitest 5); `pip-audit` reports no known vulnerabilities; CI updated to `npm ci`, lint, UI tests, npm audit and pip-audit jobs. Pending: first GitHub run of the changed workflows (CI VERIFIED not yet claimed). | Deterministic dependency installation, lockfile, broader UI/E2E tests, lint and dependency/security scanning. | None for local scope. | Clean CI install, lockfile consistency, UI reports and scan results (CI run pending). |
| ASAA-009 | P1 | PARTIALLY COMPLETE | `scripts/load_test.py` (spawned API, generated RS256 tokens, asyncio/httpx mixed workload, percentiles, error rate, budget exit code) and local measurements recorded in TESTING section 4 (e.g. PostgreSQL 18, 2 workers, 20 concurrent: 66 rps, p95 978 ms, 0 errors). No approved budgets, target infrastructure, pool-saturation or soak results. | Define budgets and validate load, concurrency, pool saturation and capacity. | Target infrastructure and workload profile. | Reproducible load-test report on target infrastructure and remediation evidence. |
| ASAA-010 | P1 | PARTIALLY COMPLETE | Post-deploy `scripts/smoke_test.py` (tested against a spawned API and an unreachable target), manual `release-smoke.yml` workflow, production hardening (docs/OpenAPI disabled, `/metrics` gated, security headers, 1 MiB body limit). No deployment workflow, environments, approvals or rollback exist because no hosting target is selected. | Approved environment promotion, approvals, smoke tests and rollback/forward recovery. | Hosting and release ownership. | Non-production deployment rehearsal with rollback evidence. |
| ASAA-011 | P1 | PARTIALLY COMPLETE | `/health`, `/ready` (database check, 503 without detail leakage), request IDs, JSON logs with key- and pattern-based redaction, access log without query strings, Prometheus-format `/metrics` (route-template labels, token protected, hidden in production), identity dead-letter ERROR log. 13 local tests pass. No log shipping, dashboards, alert routing, traces or runbooks on a live platform. | Centralized redacted logs, metrics, traces, alert routing, incident runbooks and backup monitoring. | Hosting/monitoring provider and operational owners. | Injected-failure alert tests and operational review. |
| ASAA-012 | P1 | BLOCKED BY EXTERNAL DEPENDENCY | Only main/new/docs branch observed; main/new reported unprotected; branch protection and creation of dev/fix/test need repository administration and were intentionally not performed in this engineering increment. | Establish five-branch standard and review/status gates without rewriting history or merging unapproved work. | Owner/repo administration permission. | Branch inventory, protection/ruleset inspection and PR workflow test. |

## 6. Current release decision

**NO-GO for production.** (re-evaluated 2026-11-13 after the engineering increment; no P0 external gate changed state.) P0 database provisioning, real provider activation, identity lifecycle, security assurance, recovery and business acceptance are not closed. P1 workflows must be accepted in scope or explicitly disabled/excluded before launch.

A successful PostgreSQL CI run proves only that the tested migration/API behavior worked against the disposable CI database at the recorded commit. It does not prove production TLS, least privilege, capacity, backup, restore, monitoring or UAT.

## 7. Verified closure increments

### ASAA-013 — Enforce HTTPS for OIDC JWKS retrieval
**Status:** CI VERIFIED. The OIDC browser client now applies the secure-endpoint policy to the JWKS URI as well as authorization and token endpoints. Four Node.js tests passed (HTTPS, localhost development exception, remote HTTP rejection and non-HTTP scheme rejection), and the Vite production build passed in [web CI run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233) at commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c`. This does not close provider activation or end-to-end SSO/MFA acceptance.

### 2026-11-13 engineering increment (branch `new`)
**Status:** locally verified; not yet CI VERIFIED. Environment: Windows 11, Python 3.14.7, Node 24, local PostgreSQL 18 (disposable cluster), no external services.

| Check | Initial (start of increment) | Final |
|---|---|---|
| API pytest, SQLite only | 68 passed, 1 skipped | 123 passed, 2 skipped |
| API pytest, PostgreSQL enabled | not run | 125 passed, 0 skipped (fresh PostgreSQL 18 database) |
| `npm run test:web` | 4 passed | 4 passed |
| `npm run test:ui` | none | 17 passed (2 files) |
| `npm run lint` | no script | 0 errors, 0 warnings (initial lint run: 24 errors, 8 warnings) |
| `npm run build` | passed | passed |
| `npm audit --audit-level=high` | 0 vulnerabilities (before test deps) | 0 vulnerabilities |
| `pip-audit` | not run | no known vulnerabilities |
| Real-browser E2E | none | none (not implemented) |
| Alembic | 15 revisions | 16 revisions; upgrade/downgrade/re-upgrade on PostgreSQL 18 |

Defects found and fixed: (1) the portal crashed (`reduce` of undefined) for sessions holding only some read permissions; (2) the portal displayed "API connected" after a 401 had cleared the session; (3) unnamed icon-only buttons (axe `button-name`, critical) and a dialog without role/Escape handling; (4) `package-lock.json` was git-ignored so `npm ci` could not work in CI; (5) the first Vitest version selected pulled in critical advisories (found by `npm audit`, replaced). No API authorization defect was found by the new negative tests.

Commits: see `git log` on `new` after `fc5bba5` (web tooling and UI tests; API security/observability/backup/load; identity provisioning; hardening/smoke/CI; documentation).

## 8. Delivery update protocol

After each increment:
1. Record exact branch and commit.
2. Record files and behavior changed.
3. Record test command/workflow, environment and result.
4. Update the relevant gap status and evidence.
5. Re-score only dimensions materially affected by verified evidence.
6. Record regressions, limitations and owner dependencies.
7. Re-evaluate release gates.

Do not change this baseline silently. Preserve prior dated assessment records when superseded.
