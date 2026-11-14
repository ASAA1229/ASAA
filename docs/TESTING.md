# ASAA Testing and Quality Strategy

**Current results and gap states:** [Project Status](PROJECT_STATUS.md).  
**Rule:** Test evidence is tied to an exact commit and environment. Source presence is not a pass.

## 1. Test layers

| Layer | Required coverage | Current repository evidence |
|---|---|---|
| Static/compile | Python compile, frontend build, lint/type checks | Python compile in API CI; Vite production build; ESLint flat config (`npm run lint`) with 0 errors and 0 warnings locally (2026-11-13). No TypeScript/type-check layer (JavaScript/JSX). |
| Unit | Domain rules, schemas, state transitions, calculations | API pytest suite; coverage percentage not recorded. |
| API/integration | Authentication, authorization, CRUD, workflow transitions, errors and audit | API suite: 159 passed with PostgreSQL integration enabled, 153 passed, 6 skipped without PostgreSQL (local, 2026-11-14). |
| Database/migrations | Upgrade, downgrade/re-upgrade, constraints, transaction and concurrency behavior | SQLite migration checks and PostgreSQL 16 CI (earlier commit); local PostgreSQL 18 upgrade/downgrade/re-upgrade of all 16 revisions and PostgreSQL integration tests passed locally. |
| UI/component | Rendering, validation, role-aware controls, errors and accessibility semantics | 17 Vitest + Testing Library (jsdom) tests plus 4 Node.js OIDC policy tests, run locally. |
| E2E | Real user journeys across UI/API/database | Playwright against `vite preview` and a live local API (fresh SQLite, per-run RSA key): launch workflows on Chromium, Firefox and WebKit; responsive/reflow checks at 320 px and 640 px on Chromium and Pixel 5 / iPhone 13 emulation. 96 passed, 2 skipped, 1 failed (WebKit does not Tab to links) in the first full run across five projects; after skipping that one test for WebKit, WebKit launch suite 18 passed; Chromium+mobile reflow/device suite 40 passed, 2 skipped. Local only so far; no physical devices. |
| Security | Authentication, MFA, tenant isolation, IDOR, privilege escalation, SoD, sensitive fields, audit | `tests/test_security_negative.py` (15 tests) plus existing security/authorization tests; independent assurance pending. |
| Performance | Load, stress, soak, concurrency, pool/capacity and response budgets | `apps/ap-api/scripts/load_test.py` with recorded local numbers (section 4). No soak, no target-infrastructure evidence, no approved budgets. |
| Accessibility/compatibility | Keyboard, screen reader, contrast, zoom, responsive layout, browsers/devices | Real-browser axe (colour contrast included) on three engines, keyboard-only checks, 320 px reflow, 640 px (200% zoom equivalent) and touch-target checks. No screen reader, native browser zoom or physical device evidence. |
| Operational | Deployment smoke, alerts, backup/restore, rollback and DR | Smoke script tested against a spawned API; encrypted backup, retention, scheduled run and staleness checks tested; alert rules statically checked (promtool run by CI only); deployment rehearsal scripted but NOT RUN locally (Docker daemon not running). No live alerting or DR exercise. |
| Business acceptance | Approved finance, HR, payroll, procurement and governance scenarios | Owner acceptance pending. |

## 2. Current CI workflows

The workflow definitions below were changed on 2026-11-13. They have been validated for YAML syntax only; **no GitHub Actions run has been recorded for the changed definitions yet**. The older run links remain evidence for the earlier commits only.

### API quality
Workflow: `.github/workflows/people-api-ci.yml`

- Python 3.12; install, compile, pytest, SQLite Alembic upgrade/downgrade/re-upgrade.
- Job `python-dependency-audit`: `pip-audit` on the installed dependency set.
- (PostgreSQL workflow) a load run with `monitoring/performance-budget.json` as a provisional gate, result uploaded.
- Job `local-load-and-smoke`: spawns the API, runs the 20 s load script with a generous p95 regression budget and uploads the JSON result.

Latest recorded successful run (earlier commit): [43411431405](https://github.com/ASAA1229/ASAA/actions/runs/43411431405), commit `ba87df7fdb967adf80d00b7b4771a823708b7582`.

### PostgreSQL integration
Workflow: `.github/workflows/postgres-integration.yml` (unchanged): disposable PostgreSQL 16, all migrations, complete API suite (which now also includes the PostgreSQL backup round-trip test when `pg_dump`/`pg_restore` are present), downgrade/re-upgrade.

Latest recorded successful run (earlier commit): [43411431368](https://github.com/ASAA1229/ASAA/actions/runs/43411431368).

### Web
Workflow: `.github/workflows/portal-ci.yml`

- Node.js 22, `npm ci` (lockfile now tracked), `npm run lint`, `npm run test:web`, `npm run test:ui`, `npm run build`.
- Job `web-dependency-audit`: `npm audit --audit-level=high`.
- Latest recorded successful run (earlier commit): [43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233).

### Web E2E
Job `web-e2e` in `portal-ci.yml`: installs the API, Chromium and runs `npx playwright test` (builds the app, serves it with `vite preview`, starts `scripts/e2e_api.py`). Uploads the Playwright report. Configured, **not yet run on GitHub**; the same suite passed locally (see Project Status section 7).

### Monitoring rules
Workflow `.github/workflows/monitoring-ci.yml` runs `promtool check rules` and `promtool test rules` (official Prometheus image). Not yet run on GitHub; not run locally.

### Deployment rehearsal
Workflow `.github/workflows/deploy-rehearsal.yml` runs `deploy/rehearsal.sh` (migrate, smoke, bad release, rollback, smoke) on the runner and uploads `rehearsal-result.json`. Not yet run anywhere.

### Post-deploy smoke
Workflow: `.github/workflows/release-smoke.yml` (manual `workflow_dispatch`, read-only). It performs no deployment.

## 3. Local verification commands

From repository root:

```bash
npm ci
npm run lint
npm run test:web      # Node.js OIDC transport-policy tests
npm run test:ui       # Vitest + Testing Library + axe (jsdom)
npx playwright install chromium firefox webkit   # once
npm run test:e2e      # all projects: chromium, firefox, webkit, mobile-chrome, mobile-safari
npx playwright test --project=chromium responsive   # reflow checks only
npm run build
npm audit --audit-level=high
```

From `apps/ap-api` after creating the virtual environment and installing `.[test]`:

```bash
python -m compileall -q src tests
python -m pytest -q
python -m alembic upgrade head
python -m alembic current
python -m pip_audit --skip-editable
python scripts/load_test.py --concurrency 20 --duration 20
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
python scripts/backup_restore.py keygen            # base64 AES-256 key; store in a secret manager
python scripts/backup_restore.py scheduled --database-url sqlite:///./asaa_ap.db --out backups/ --encrypt-key-file env:ASAA_BACKUP_KEY
python scripts/backup_restore.py check-staleness --out backups/ --max-age-hours 26   # exit 2 = alert
python scripts/load_test.py --concurrency 20 --duration 20 --workers 2 --database-url postgresql+psycopg://... --budget-file ../../monitoring/performance-budget.json
bash deploy/rehearsal.sh   # needs a running Docker daemon
python scripts/db_roles.py provision --admin-url postgresql://admin@host/db   # needs ASAA_DB_*_PASSWORD env
PGPASSWORD=... python scripts/db_roles.py check --runtime-url postgresql://asaa_runtime@host/db
```

PostgreSQL-dependent tests run only when `ASAA_AP_POSTGRES_TEST_URL` (and, for the integration module, an identical `ASAA_AP_DATABASE_URL`) point at a **disposable, freshly migrated** PostgreSQL database. The integration module uses fixed business keys, so a second run against the same database fails with HTTP 409 until the database is recreated. The integration module now uses a unique organization per run, so reruns no longer collide. Role-separation tests (`tests/test_db_privileges.py`) create and drop their own database and roles and need an administrative test URL. Use only a disposable local/test database for downgrade/re-upgrade and restore tests.

## 4. Local measurements recorded 2026-11-13

Environment: Windows 11, 12 logical CPUs, Python 3.14.7, API and load generator on the same machine, 20 s runs after warm-up, mixed workload (5% health, 5% ready, 55% list suppliers, 25% create supplier, 10% audit events), authenticated with generated RS256 tokens. **These are local development-machine numbers; they are not capacity or performance acceptance evidence.**

| Database | API workers | Concurrency | Requests | Throughput | p50 | p95 | p99 | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SQLite (temp file) | 1 | 10 | 714 | 35.4 rps | 154 ms | 903 ms | 1,978 ms | 0 |
| SQLite (temp file) | 1 | 50 | 1,746 | 85.8 rps | 404 ms | 1,635 ms | 2,696 ms | 0 |
| PostgreSQL 18 (local) | 2 | 20 | 1,338 | 66.0 rps | 180 ms | 978 ms | 1,769 ms | 0 |

Later PostgreSQL 18 runs on the same machine under heavier background load (2 workers, 20 clients, 20 s, 0 errors): 616 req / 30.4 rps / p50 379 ms / p95 1,909 ms / p99 2,886 ms; 656 req / 31.4 rps / p95 2,062 ms; 630 req / 31.0 rps / p95 1,904 ms. The spread between 978 ms and ~2,000 ms p95 on identical code shows how sensitive these numbers are to machine load; the CI budget therefore carries headroom (see `monitoring/performance-budget.json`).

Even `/health` showed >100 ms median latency under this load, so the numbers are dominated by single-machine CPU contention and Windows process scheduling rather than by the database.

## 5. Required release test evidence

- Exact commit SHA and environment.
- Workflow/run URL or reproducible command and captured output.
- Test count, pass/fail/skip counts and coverage where measured.
- Database engine/version and migration revision.
- Test data classification and cleanup result.
- Defect IDs, severity and disposition.
- Reviewer and owner acceptance where required.

## 6. Quality gate

A release candidate must pass all tests relevant to the enabled scope. P0 security, data-integrity, authorization, recovery and critical workflow defects block release. UI/E2E, accessibility, performance, compatibility and operational tests must be completed for included workflows or the affected capability must be disabled/excluded with explicit owner acceptance.

Do not invent coverage percentages or convert skipped tests into passed tests.
