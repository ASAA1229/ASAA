# ASAA Testing and Quality Strategy

**Current results and gap states:** [Project Status](PROJECT_STATUS.md).  
**Rule:** Test evidence is tied to an exact commit and environment. Source presence is not a pass.

## 1. Test layers

| Layer | Required coverage | Current repository evidence |
|---|---|---|
| Static/compile | Python compile, frontend build, lint/type checks | Python compile in API CI; web build workflow configured; frontend lint/type scripts absent. |
| Unit | Domain rules, schemas, state transitions, calculations | API pytest suite exists; coverage percentage not recorded. |
| API/integration | Authentication, authorization, CRUD, workflow transitions, errors and audit | API tests exist and full suite passed in recorded CI. |
| Database/migrations | Upgrade, downgrade/re-upgrade, constraints, transaction and concurrency behavior | SQLite migration checks and PostgreSQL 16 migration/integration CI passed. |
| UI/component | Rendering, validation, role-aware controls, errors and accessibility semantics | No frontend test suite evidenced. |
| E2E | Real user journeys across UI/API/database | Not evidenced. |
| Security | Authentication, MFA, tenant isolation, IDOR, privilege escalation, SoD, sensitive fields, audit | Focused API security/authorization tests exist; full independent assurance pending. |
| Performance | Load, stress, soak, concurrency, pool/capacity and response budgets | Not evidenced. |
| Accessibility/compatibility | Keyboard, screen reader, contrast, zoom, responsive layout, browsers/devices | Not evidenced. |
| Operational | Deployment smoke, alerts, backup/restore, rollback and DR | Not evidenced. |
| Business acceptance | Approved finance, HR, payroll, procurement and governance scenarios | Owner acceptance pending. |

## 2. Current CI workflows

### API quality
Workflow: `.github/workflows/people-api-ci.yml`

- Python 3.12.
- Installs API/test dependencies.
- Compiles source and tests.
- Runs pytest.
- Performs SQLite Alembic upgrade, downgrade and re-upgrade.

Latest inspected successful run: [43411431405](https://github.com/ASAA1229/ASAA/actions/runs/43411431405), commit `ba87df7fdb967adf80d00b7b4771a823708b7582`.

### PostgreSQL integration
Workflow: `.github/workflows/postgres-integration.yml`

- Starts a disposable PostgreSQL 16 service.
- Applies all migrations and checks current revision.
- Runs complete API tests including PostgreSQL-specific people/payroll persistence.
- Performs downgrade/re-upgrade.

Latest inspected successful run: [43411431368](https://github.com/ASAA1229/ASAA/actions/runs/43411431368), commit `ba87df7fdb967adf80d00b7b4771a823708b7582`.

### Web build
Workflow: `.github/workflows/portal-ci.yml`

- Uses Node.js 22.
- Runs `npm install` and `npm run build`.
- A successful run matching the assessed head was not established in this baseline.
- No root lockfile, frontend test or lint script was found in the inspected tree.

## 3. Local verification commands

From repository root:

```bash
npm install
npm run build
```

From `apps/ap-api` after creating/activating the virtual environment and installing `.[test]`:

```bash
python -m compileall -q src tests
python -m pytest -q
python -m alembic upgrade head
python -m alembic current
```

Use only a disposable local/test database for downgrade/re-upgrade. Never run destructive migration checks against production.

## 4. Required release test evidence

- Exact commit SHA and environment.
- Workflow/run URL or reproducible command and captured output.
- Test count, pass/fail/skip counts and coverage where measured.
- Database engine/version and migration revision.
- Test data classification and cleanup result.
- Defect IDs, severity and disposition.
- Reviewer and owner acceptance where required.

## 5. Quality gate

A release candidate must pass all tests relevant to the enabled scope. P0 security, data-integrity, authorization, recovery and critical workflow defects block release. UI/E2E, accessibility, performance, compatibility and operational tests must be completed for included workflows or the affected capability must be disabled/excluded with explicit owner acceptance.

Do not invent coverage percentages or convert skipped tests into passed tests.
