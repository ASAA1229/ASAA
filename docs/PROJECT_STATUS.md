# ASAA Project Status — Authoritative Baseline

**As of:** 2026-11-13  
**Assessed branch:** `new`  
**Initial assessment head:** `3257d883382f8cf7591457f29d267f0ebd4d7d08`  
**Latest verified application commit:** `69e08b2b591cc570d0af0eb4d8121cb32989b00c`  
**Latest documentation refresh:** 2026-11-13 (engineering increment on branch `new`, commits after `fc5bba5`)  
**Initial maturity:** 4.5/10; **after first verified increment:** 4.6/10; **current after the 2026-11-13/14 engineering increments:** 5.9/10 (equal-weight average of 11 dimensions; local evidence only, see section 3)  
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
| Implementation completeness | 5.5 | 6.0 | 6.3 | Adds a standards-based SCIM 2.0 adapter (tested against a local fake server only), encrypted/rotated/scheduled backups, alert rules, deployment rehearsal assets. Real provider, document storage, notifications, procure-to-pay and policy engines remain absent. |
| Unit, integration, API, UI and E2E testing | 6.5 | 8.0 | 8.2 | Local: API 159 passed with PostgreSQL / 153 passed, 6 skipped without; 17 jsdom + 4 Node tests; real-browser E2E on Chromium, Firefox and WebKit plus Pixel 5/iPhone 13 emulation and 320px/640px reflow checks (see section 7). No CI run yet for the new commits; no physical devices. |
| Security and privacy | 5.0 | 6.2 | 6.5 | Adds least-privilege PostgreSQL role provisioning/check (runtime cannot DDL, write alembic_version or modify audit rows) tested on PostgreSQL 18, and `/api/v1/me` so the portal verifies tokens server-side. Independent review, provider/MFA activation, production audit immutability remain. |
| Performance and scalability | 4.0 | 5.0 | 5.4 | PostgreSQL load run with a provisional p95/p99/error/throughput budget gate wired into the PostgreSQL CI workflow; local runs 978-2,062 ms p95 depending on machine load. Budgets are not owner-approved SLOs; no target infrastructure. |
| Accessibility and compatibility | 3.5 | 6.0 | 6.8 | Real-browser axe on Chromium, Firefox and WebKit; keyboard checks; 320px reflow and 640px (200% zoom equivalent) with no page-level horizontal scroll; scrollable table regions made keyboard-focusable; touch target minimum. No screen reader, native browser zoom, physical devices. |
| CI/CD and DevOps | 5.5 | 6.8 | 7.0 | Adds promtool (Docker) rule check/test workflow, deployment-rehearsal workflow and PostgreSQL load-budget step. All configured, none run on GitHub yet. |
| Deployment and infrastructure readiness | 2.5 | 3.0 | 3.4 | API and portal Dockerfiles, rehearsal compose stack and scripted migrate/smoke/bad-release/rollback/smoke. NOT RUN: Docker daemon was not running locally; compose config and shell syntax validated only. No hosting target. |
| Monitoring, backup and disaster recovery | 2.0 | 4.0 | 4.8 | AES-256-GCM encrypted backups with key from env, grandfather-father-son retention, scheduled entrypoint with staleness check (exit code 2 for monitoring), Prometheus alert rules with promtool unit tests (promtool not run locally) and a JSON log schema test. No live collector, alert routing, scheduler runner, off-site storage or approved RPO/RTO. |
| Release readiness and operational support | 2.5 | 2.7 | 3.2 | Gate evidence is clearer; P0 external gates are unchanged. Still NO-GO. |

Scores are repository maturity judgements (not the organization-wide score). The 2026-11-13 re-score uses only evidence listed in this document; items validated locally and not yet in CI are scored conservatively.

## 4. Verified repository baseline

### Branches and pull requests
- Default branch: `main`.
- Branches observed in the 2026-11-19 organization audit: `main`, `dev`, `new`, `fix`, `test`, and `docs/2026-11-14-master-baseline-refresh`.
- The five required ASAA branches now exist. This supersedes the earlier first-assessment note that `dev`, `fix` and `test` were absent.
- Branch protection and required-check/ruleset configuration have not been fully verified for every branch; do not infer protection from branch existence.
- GitHub compare on 2026-11-19 showed `new` and `main` had diverged (90 commits ahead, 1 behind at that snapshot). Re-run compare and review the complete diff before integration; do not merge solely on this historical count.
- No open pull requests were returned by the repository's open-PR listing during the 2026-11-19 audit. Recheck before any integration decision.

### Application and data
- Frontend: React 18, Vite 6, JavaScript/JSX.
- API: Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, PyJWT.
- Database: local SQLite default; PostgreSQL 16 integration workflow; 16 Alembic revisions (0016 adds identity sync tables; see the 2026-11-13 record below).
- API tests are present under `apps/ap-api/tests`, including security, authorization, people, AP/AR, governance and PostgreSQL integration.
- Web: `npm run test:web` (4 Node.js OIDC policy tests), `npm run test:ui` (17 Vitest/Testing Library/axe tests), `npm run lint` (ESLint flat config) and `npm run build`. `package-lock.json` is now tracked (it was previously git-ignored) and CI uses `npm ci`. A Playwright real-browser E2E suite was added on 2026-11-14 (section 7).
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
| ASAA-003 | P0 | PARTIALLY COMPLETE | Outbox, mock provider, retry/dead-letter and reconciliation (earlier) plus `asaa_identity/scim.py`: SCIM 2.0 Users/Groups create, PATCH, deactivate, filter lookup, paging, ETag/If-Match with one re-read on 412, 429 Retry-After and 5xx/timeout exponential backoff with jitter, permanent errors for other 4xx, HTTPS enforced for non-localhost, selected only by configuration (`ASAA_AP_IDENTITY_PROVIDER=scim`, `ASAA_AP_SCIM_BASE_URL`, `ASAA_AP_SCIM_BEARER_TOKEN`, `ASAA_AP_SCIM_GROUP_PREFIX`). 14 adapter tests against a local fake SCIM server including the full outbox/reconciliation/leaver flow pass. No real provider sandbox was available: vendor behaviour (User.groups support, PATCH semantics, session revocation API) is unverified. | Reliable joiner/mover/leaver sync, revocation, retries, reconciliation and failure alerts against the real provider. | ASAA-002; authoritative employee/access mapping; provider SCIM endpoint and credentials. | Integration tests against provider sandbox and lifecycle reconciliation report (not possible without a provider). |
| ASAA-004 | P0 | PARTIALLY COMPLETE | 15 negative API security tests pass locally (see 2026-11-13 record). Added `scripts/db_roles.py` and `tests/test_db_privileges.py` (4 tests on PostgreSQL 18): separate migration and runtime roles; the runtime role has no DDL, cannot write `alembic_version`, cannot update/delete `audit_events` (append-only) and the application runs end to end under it; the checker is shown to fail an over-privileged role. PostgreSQL integration test is now rerunnable. Not done: independent security review, approval of the production role matrix, tamper-evident audit retention. | Verify tenant/record/field isolation, payroll restrictions, SoD, audit-write failure behavior and privileged access controls. | Approved role matrix, data classification and policy; independent reviewer. | Negative API tests and DB privilege checks (done locally); independent security review and production DB privilege review (pending). |
| ASAA-005 | P0 | PARTIALLY COMPLETE | `scripts/backup_restore.py`: SQLite online backup and PostgreSQL pg_dump/pg_restore; SHA-256 manifest and row-count/Alembic verification; AES-256-GCM authenticated 1 MiB frames with key from `env:VARIABLE` or file (tampering, reordering, truncation and wrong key detected); grandfather-father-son retention (never prunes the newest, never prunes after a failed run); `scheduled` entrypoint (backup, verify, rotate, status file); `check-staleness` exits 2 for no/failed/stale/missing backups. 14 local tests plus a PostgreSQL 18 round trip pass. Not done: approved RPO/RTO/retention values, a scheduler to run the entrypoint, key custody, off-site storage, alert routing, timed restore at production scale. | Approved RPO/RTO/retention; encrypted automated backups; alerts; isolated restore and integrity verification. | Hosting/storage, owner-approved recovery objectives, key custody. | Timed restore exercise and evidence record on the real environment. |
| ASAA-006 | P0 | BLOCKED BY EXTERNAL DEPENDENCY | Workflows and UI foundations exist; policy and business UAT are not accepted. No engineering action can close this. | Approve organization/authority, HR/leave, payroll, procurement and finance rules; complete first-release UAT. | Named business owners and policy decisions. | Scripted UAT, signed outcomes and defect disposition. |
| ASAA-007 | P1 | PARTIALLY COMPLETE | 17 jsdom tests plus Playwright E2E against the production build and a live local API: launch workflow spec on Chromium, Firefox and WebKit (axe WCAG 2 A/AA + best-practice incl. contrast, keyboard checks; the skip-link test is skipped on WebKit, which does not Tab to links by default); responsive spec at 320 px (reflow) and 640 px (200% zoom equivalent; Playwright cannot drive native zoom) on Chromium plus Pixel 5 and iPhone 13 emulation, asserting no page-level horizontal scroll, axe, working navigation menu, 24 px touch targets. Results: 96 passed, 2 skipped, 1 failed (WebKit does not Tab to links) in the first full run across five projects; after skipping that one test for WebKit, WebKit launch suite 18 passed; Chromium+mobile reflow/device suite 40 passed, 2 skipped. Defects found and fixed: 7 px overflow of dashboard panels at 320 px, scrollable table regions not keyboard-focusable, 16 px-high text-link targets. Not done: screen reader, native zoom, physical devices, Safari proper (WebKit engine only), and the `web-e2e` CI job has not run on GitHub. | Launch-workflow UI/E2E regression, keyboard/screen-reader and supported-browser/device tests. | Stable launch scope, real devices, supported-browser decision. | Automated reports (done locally) and manual accessibility/device records (pending). |
| ASAA-008 | P1 | COMPLETE AND VERIFIED (locally tested) | `package-lock.json` is tracked (was git-ignored); `npm ci` succeeds; ESLint flat config, `npm run lint` = 0 problems; `npm audit --audit-level=high` = 0 vulnerabilities (a vulnerable Vitest 3 dependency chain was caught by the audit and replaced by Vitest 5); `pip-audit` reports no known vulnerabilities; CI updated to `npm ci`, lint, UI tests, npm audit and pip-audit jobs. Pending: first GitHub run of the changed workflows (CI VERIFIED not yet claimed). | Deterministic dependency installation, lockfile, broader UI/E2E tests, lint and dependency/security scanning. | None for local scope. | Clean CI install, lockfile consistency, UI reports and scan results (CI run pending). |
| ASAA-009 | P1 | PARTIALLY COMPLETE | `scripts/load_test.py` with `--budget-file`; `monitoring/performance-budget.json` (provisional: overall p95 3,000 ms, p99 5,000 ms, error rate 1%, throughput >= 10 rps, per-operation p95) is enforced by a step in the PostgreSQL CI workflow with the result uploaded as an artifact. Local PostgreSQL 18, 2 workers, 20 clients, 20 s: 66 rps / p95 978 ms (earlier, quiet machine), then 30.4 / 31.4 / 31.0 rps with p95 1,909 / 2,062 / 1,904 ms on a busier machine; 0 errors; budget gate exit 0. The budget is calibrated headroom, not an owner-approved SLO; no target infrastructure, saturation or soak results. | Define budgets and validate load, concurrency, pool saturation and capacity. | Target infrastructure and workload profile; owner-approved SLOs. | Reproducible load-test report on target infrastructure and remediation evidence. |
| ASAA-010 | P1 | PARTIALLY COMPLETE | Smoke script, `release-smoke.yml`, production hardening (earlier) plus `apps/ap-api/Dockerfile` (non-root, healthcheck), `Dockerfile.portal` (nginx), `deploy/docker-compose.yml` (Postgres, one-shot migrate, API, portal) and `deploy/rehearsal.sh`: build release 1 and a deliberately broken release 2, migrate, deploy, smoke (production mode), write data, deploy the bad release, expect the smoke test to fail, roll back to the previous image tag, smoke again, verify data and schema revision unchanged; run in CI by `deploy-rehearsal.yml`. **NOT RUN LOCALLY: the Docker daemon was not running** (the script exits 3 with that message); only compose config and bash syntax were validated. No hosting target, approvals or real environments. | Approved environment promotion, approvals, smoke tests and rollback/forward recovery. | Hosting and release ownership. | Non-production deployment rehearsal with rollback evidence (first run pending Docker/CI). |
| ASAA-011 | P1 | PARTIALLY COMPLETE | Health/readiness, request IDs, redacted JSON logs, `/metrics` (earlier) plus `monitoring/asaa-alerts.yml` (down, 5xx ratio, p95 latency, 401/403 spike, in-flight saturation, restart loop), `monitoring/asaa-alerts.test.yml` promtool unit tests, `monitoring/log-schema.json` and 7 local tests (rule structure and annotations, metrics referenced exist in `/metrics`, every alert has a firing test, real log lines validate against the schema, leaky lines are rejected). promtool itself was NOT run locally (no binary installed; running a downloaded unverified binary was not permitted); `monitoring-ci.yml` runs `promtool check rules` and `test rules` in the official Docker image on GitHub. No log collector, dashboards, alert routing, on-call or runbooks beyond document anchors. | Centralized redacted logs, metrics, traces, alert routing, incident runbooks and backup monitoring. | Hosting/monitoring provider and operational owners. | Injected-failure alert tests and operational review. |
| ASAA-012 | P1 | PARTIALLY COMPLETE | Verified on origin 2026-11-14: `main`, `new`, `dev`, `fix`, `test` all exist; `dev`, `fix` and `test` point at the same commit as `main` (9d9bdb2). They were not created by this increment (already present). Branch protection/rulesets and required checks are not configured and need repository administration (not performed). | Establish five-branch standard and review/status gates without rewriting history or merging unapproved work. | Owner/repo administration permission for protection/rulesets. | Ruleset inspection and PR workflow test (pending administrator). |

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

### 2026-11-14 follow-up increment (branch `new`)
**Status:** locally verified; not yet CI VERIFIED. Same environment as above.

| Check | Result |
|---|---|
| API pytest, SQLite only | 124 passed, 6 skipped (PostgreSQL-only tests skipped) |
| API pytest, PostgreSQL 18 enabled (fresh database) | 130 passed |
| `npm run test:web` / `test:ui` | 4 passed / 17 passed |
| `npm run lint` / `npm run build` / `npm audit --audit-level=high` | 0 problems / passed / 0 vulnerabilities |
| `npx playwright test` (Chromium 158, Playwright 1.65, live local API) | 19 passed |

Defects found by the real-browser run and fixed: (1) the portal reported "API connected" for any pasted string because no API call was made when the token carried no permission claims; it now calls the new authenticated `/api/v1/me` first and returns to sign-in on 401; (2) several workspace forms used undefined CSS variables and rendered white panels with light text (contrast 1.15:1) — variables defined for the dark theme; (3) 28 muted-text colour declarations below WCAG AA contrast raised; (4) toast notifications were not a live region; (5) no skip link, no dialog focus management/return, no visible keyboard focus style — added. The Playwright upgrade from 1.49 to 1.65 was required by `npm audit` (high advisory on browser download verification).

Hygiene: a generated `.e2e/tokens.json` had been committed by another actor (9797c1a); it is untracked again and `.e2e/` is ignored. The launcher generates a fresh RSA key and 30-minute tokens on every run and writes them only to the ignored path.

### 2026-11-14 second follow-up increment (branch `new`)
**Status:** locally verified except where marked NOT RUN; not CI VERIFIED. Same environment as above, plus Chromium, Firefox and WebKit from Playwright 1.65.

| Check | Result |
|---|---|
| API pytest, SQLite only | 153 passed, 6 skipped |
| API pytest, PostgreSQL 18 enabled (fresh database) | 159 passed |
| `npm run test:web` / `test:ui` | 4 passed / 17 passed |
| `npm run lint` / `build` / `npm audit --audit-level=high` | 0 problems / passed / 0 vulnerabilities |
| Playwright, all five projects | 96 passed, 2 skipped, 1 failed (WebKit does not Tab to links) in the first full run across five projects; after skipping that one test for WebKit, WebKit launch suite 18 passed; Chromium+mobile reflow/device suite 40 passed, 2 skipped |
| promtool (rule check and unit tests) | NOT RUN locally; configured in `monitoring-ci.yml` |
| Container deployment rehearsal | NOT RUN locally (Docker daemon not running); configured in `deploy-rehearsal.yml` |

New components: SCIM 2.0 adapter, AES-256-GCM backups with retention/scheduling/staleness, Prometheus alert rules and JSON log schema, provisional PostgreSQL performance budget gate, Docker/compose rehearsal, Firefox/WebKit/mobile/reflow E2E projects. Defects found by the new tests and fixed: dashboard panels overflowed the viewport by 7 px at 320 px; horizontally scrollable tables were not keyboard-focusable; small text-link targets; the SCIM adapter's filter escaping and retry timing were validated against the fake server (two test-side expectation errors corrected, no adapter defect).

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


---

## ASAA Master Requirements Baseline v1.0 (2026-11-14)

The organization-approved planning and governance baseline now covers ASAA, Portfolio, JARVIS, Templates and shared ecosystem capabilities. Round 6 (12 consolidation stages) is complete at framework/consolidation level. This approval does not imply that individual requirements, all 1,000 source answers, repository evidence, named owners, dependencies, gaps, estimates or delivery dates have been fully validated.

See `docs/ASAA_MASTER_REQUIREMENTS_BASELINE.md`, `docs/PROJECT_SCOPE.md` and `docs/EPIC_STATUS.md`. Outstanding source reconciliation, requirement population, repository/runtime evidence, owner/dependency validation, evidence-based gap analysis and delivery estimates remain pending. This is a planning baseline only; it does not authorize implementation, testing, deployment, paid services or merges.

## ASAA Master Requirements Baseline v1.0 — 2026-11-14

**Governance state: APPROVED for planning and requirements governance only.** The baseline covers ASAA organization, Portfolio, JARVIS, Templates and shared ecosystem capabilities. Approval does not authorize coding, testing, repository implementation changes beyond this documentation update, deployment, paid services, merges or releases.

Round 6 consolidation is complete at framework level (12/12 stages). Discovery history records five rounds, 50 sets and 1,000 questions, all answered with all options selected. Those selections represent desired target requirements, not proof that every requirement applies to every project or that implementation exists.

### Required distinctions
- Keep organization-wide, shared, project-specific, cross-project, future/conditional, external and not-applicable requirements separately classified.
- Preserve existing verified work. Do not restart or rewrite projects solely to align with the baseline.
- Distinguish planned, in development, implemented-unverified, tested, integrated, owner-accepted and released-operational states.
- A code artifact, user report, passing test or CI run alone does not prove full workflow acceptance or production operation.
- Maintain bidirectional traceability: discovery source → requirement → project/module → epic → acceptance criteria → implementation → tests → evidence → approval/release.
- Use the ASAA organization branch standard: main, dev, new, fix, test. Branch presence does not imply protection/rulesets.
- Shared capabilities require explicit owner, consumers, interface, data authority, permission, versioning, operations and recovery. Shared identity does not imply unrestricted cross-project data access.
- No paid services without explicit approval; preserve project-specific cost and privacy constraints.

### Open validation items
Full question-level source reconciliation; individual normalized requirement population; exhaustive duplicate/conflict verification; detailed decision approvals; project applicability mapping; named owners and RACI; dependency graph; requirement-level acceptance criteria; repository/runtime evidence; evidence-based gap scoring; delivery estimates and milestone dates remain pending unless explicitly evidenced in this repository.

### Status recording rule
For every epic, track Development, Testing, Integration, Acceptance/Release independently. Use NOT ASSESSED where evidence is absent. COMPLETED — VERIFIED requires defined acceptance criteria, passing evidence for the stated revision/environment and authorized acceptance. RELEASED — OPERATIONAL additionally requires approved release and operational evidence.


## 2026-11-14 documentation reconciliation and head check (documentation owner)

Head inspected: `a40c7ca` (a commit by a human collaborator, "Refactor CI workflow and remove deprecated E2E API script", after the code agent's last verified commit `ac2f696`).

| Check at `a40c7ca` | Result |
|---|---|
| Coordinator-reported at `ac2f696` | lint OK, build OK, pytest SQLite 153 passed / 6 skipped (agent-reported 159 on PostgreSQL; Playwright 5 projects) |
| `npm run lint` (documentation-owner rerun) | **FAIL**: `playwright.config.js` 41:10 `Parsing error: Identifier 'defineConfig' has already been declared`. The commit appended a second, Chromium-only copy of the Playwright configuration to the existing five-project file, so the file no longer parses. |
| Same commit, `src/styles.css` | Removes the skip-link, `:focus-visible`, focusable table-region, 320 px reflow and `.text-link` target-size rules that the earlier accessibility fixes (ASAA-007) depended on. |
| Same commit, hygiene | Adds generated `.e2e-install.log` and `.e2e-result.json` to version control. |

Consequence: until the config and CSS are restored, the lint result, the Playwright E2E and the accessibility evidence recorded for `ac2f696` do not apply to head `a40c7ca`. They remain valid only for `ac2f696`. This is a code issue for the code owner, not changed by this documentation update. Environment note: the working tree also holds uncommitted work in progress (notifications module, migration 0017) that is not evidence. pytest and Playwright were not rerun by the documentation owner because of that in-progress work. No GitHub Actions run has been observed (`gh` is unauthenticated), so nothing is CI VERIFIED. Release decision unchanged: NO-GO.


## 2026-11-15 reconciliation (documentation owner)

Head at time of writing: `0dbb67b`. Evidence classes are kept apart: coordinator-verified, agent-reported, agent-pushed and pending verification, CI not observed.

| Item | Status | Evidence class |
|---|---|---|
| Repair of the a40c7ca regression (commit 37f478d): duplicate Playwright config removed, `e2e_api.py` restored, `/api/v1/me` duplicate removed, duplicated workflow path filters removed, six accessibility/reflow CSS rules restored, `*.log` ignored | repaired; supersedes the 2026-11-14 head-check section above, which stays as dated history | coordinator-verified |
| At `37f478d`: lint, build, 17 UI tests, pytest SQLite 165 passed / 6 skipped | pass | coordinator-verified |
| My lint rerun (`npm run lint`) at `0dbb67b` | pass (no ESLint errors) | documentation-owner rerun |
| Playwright 96 passed / 3 skipped across 5 projects | pass | agent-reported, not rerun by the coordinator or me |
| Docker deployment rehearsal executed locally: 13/13 steps passed, with `API_PORT=18000 PORTAL_PORT=18080` because port 8080 is reserved on some Windows hosts (commit decebcc) | first real run; supersedes "NOT RUN" in ASAA-010 and in the 2026-11-14 second follow-up table | agent-reported |
| `promtool check rules` and `test rules` via the `prom/prometheus:v2.55.1` image | passed locally | agent-reported |
| Notification outbox (migration 0017, 12 tests; sensitive-content minimization, preferences, delivery status, retry/dead-letter, leave-review hook; commit a16459d) | implemented, tested locally | agent-reported (inside the 165) |
| Governed registers (commit 3bda274, migration 0018): policies and procedures, risk and internal controls, compliance obligations, legal contracts, privacy and retention, knowledge base, announcements, integrations and connectors, workflow and approvals (validated state graphs), security operations, operational incidents; versioned revisions, maker-checker review, per-register permissions, audit events, organization isolation | implemented with API, jsdom and Playwright tests | agent-pushed, pending verification |
| Workspace inventory (commit b1006d4): 73 workspaces in `src/workspaces/inventory.json` with a sync test; Reports and dashboards routing fixed (was 19 functional, 6 partial, 48 preview; now 20 functional) | implemented | agent-pushed, pending verification |
| `0dbb67b` audit trail view with action/actor/entity/outcome filters, notifications, governance, reports and financial-reporting workspaces; reports API aggregates per currency and per permission with lineage and freshness, never payroll or salary | implemented with tests | agent-pushed, NOT coordinator-verified |

Gap tally is unchanged (13: 2 complete and verified, 8 partial, 3 blocked). ASAA-007 evidence is restored to the 2026-11-14 level after the repair; ASAA-010 and ASAA-011 gain local execution evidence (rehearsal 13/13, promtool) but stay PARTIALLY COMPLETE because there is no hosting target, alert routing or GitHub run. The maturity score (5.9/10) was not re-scored for this batch. The release decision is NO-GO and nothing is CI VERIFIED (`gh` unauthenticated).

## Delivery phase — 2026-11-15

**Current phase: DEVELOPMENT** (owner direction: DEVELOPMENT, then TESTING, then DEPLOYMENT). Features added in this phase carry the status **IMPLEMENTED — NOT FULLY TESTED** until the testing phase runs. Test-phase and deployment-phase items that are not yet due (full-suite reruns, CI runs, hosted or staging verification, hosting, live providers, production rehearsal) are **deferred to test phase** or **deferred to deployment phase**; they are not failures. Evidence classes used in these documents: coordinator-verified, agent-reported, in progress, CI not observed.

Tracker note: the workbooks add ASAA-014 (governed registers and workspace inventory) as a tracked row with status IMPLEMENTED — NOT FULLY TESTED; verification is deferred to the test phase, so the tracked gap count is 14 (2 complete and verified, 8 partial, 3 blocked, 1 implemented not fully tested).


## 2026-11-19 CI follow-up

The organization audit inspected PostgreSQL integration run **44501324951** on `new`, SHA `2c6e39a2`: **623 passed, 1 failed**. The failure was `test_postgresql_round_trip_backup_restore_verify`. The archive was produced by a newer PostgreSQL client that emitted `SET transaction_timeout = 0;`, which PostgreSQL 16 does not recognize.

A compatibility fix was committed on `new`:
- `apps/ap-api/scripts/backup_restore.py` now renders the custom archive to SQL, removes only the unsupported newer-client session setting, then executes the compatible SQL with `psql` in a single transaction (commit `71fb683d76892e9be5477199adb462fc5555e721`).
- `apps/ap-api/tests/test_backup_restore.py` adds a focused regression test proving the filter removes that setting and preserves other SQL (commit `cd22a4cf718cd35dbcb4ff80e01018ffcb7e1694`).

Post-fix PostgreSQL integration run **44524049465** completed successfully on exact application commit `71fb683d76892e9be5477199adb462fc5555e721` (**CI VERIFIED**). The regression test and full PostgreSQL integration job passed. Run **44524049350** also completed successfully on that commit for local-load/smoke, Python dependency audit and people/finance API quality. In run **44524049436**, the web production build and dependency audit passed; the browser E2E job was still in progress at the time of this update. The earlier PostgreSQL integration failure remains historical evidence; the corrected restore path is now CI-verified for the named exact application commit. This does not change the overall **NO-GO** release decision or establish production acceptance.
