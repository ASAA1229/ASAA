# Development Guide

## 1. Repository layout

```text
ASAA/
├── README.md
├── apps/
│   └── ap-api/
│       ├── pyproject.toml
│       ├── alembic.ini
│       ├── migrations/
│       ├── src/
│       │   ├── asaa_ap/       # shared API, finance/AP/AR, security, database
│       │   ├── asaa_people/   # HR, onboarding/offboarding, payroll
│       │   └── asaa_governance/ # master data, decisions and authority register
│       └── tests/
└── docs/
    ├── ARCHITECTURE.md
    ├── REQUIREMENTS.md
    ├── DEVELOPMENT.md
    ├── OPERATIONS.md
    └── SECURITY.md
```

## 2. Prerequisites

- Python 3.11 or newer (CI currently uses Python 3.12).
- Git.
- SQLite for local/test use; PostgreSQL and an approved identity provider for shared/production environments.
- Network access to install the declared Python packages.

## 3. Local setup

From the repository root:

```bash
cd apps/ap-api
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

Install the API and test dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Create a local `.env` only when needed. The application reads settings with the `ASAA_AP_` prefix. Local SQLite is the default:

```dotenv
ASAA_AP_DATABASE_URL=sqlite:///./asaa_ap.db
ASAA_AP_JWT_PUBLIC_KEY=
ASAA_AP_JWT_ISSUER=
ASAA_AP_JWT_AUDIENCE=
```

Authenticated API routes fail closed until a valid RS256 public key, issuer and audience are configured. Use test-only signing material for local tests; never use production secrets in development.

## 4. Database migrations

Run from `apps/ap-api`:

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

Current revision chain:
- `0001_supplier_foundation`
- `0002_ar_foundation`
- `0003_people_foundation`
- `0004_onboarding_task_description`
- `0005_people_workflows`
- `0006_onboarding_template_version`
- `0007_offboarding_checklists`
- `0008_onboarding_assignment_version`
- `0009_master_data_governance`
- `0010_authority_register`

For a disposable local/test database only, the CI migration check performs:

```bash
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

Do not run downgrade commands against production without a reviewed, tested recovery plan and an approved change window. Back up before applying production migrations.

## 5. Run the API

```bash
uvicorn asaa_ap.main:app --reload
```

The local development server normally listens at `http://127.0.0.1:8000`. FastAPI interactive API documentation is normally available at `/docs`; disable or protect interactive documentation in production according to the security policy.

## 6. Tests and quality checks

Run from `apps/ap-api`:

```bash
python -m compileall -q src tests
python -m pytest -q
```

The CI workflow `.github/workflows/people-api-ci.yml`:
- Runs on pushes to `main`, `dev`, `new`, `fix`, `test` when API paths/workflow change.
- Runs on pull requests targeting `main` or `dev` when API paths/workflow change.
- Uses Python 3.12.
- Installs `.[test]`, compiles source/tests, runs pytest and checks Alembic upgrade/downgrade/upgrade on SQLite.
- Uses read-only GitHub contents permission.

SQLite CI does not replace PostgreSQL integration tests.

## 7. Configuration reference

| Variable | Purpose | Default / requirement |
|---|---|---|
| `ASAA_AP_DATABASE_URL` | SQLAlchemy database URL | Local SQLite default |
| `ASAA_AP_JWT_PUBLIC_KEY` | RS256 verification public key | Required for authenticated routes |
| `ASAA_AP_JWT_ISSUER` | Expected token issuer | Required |
| `ASAA_AP_JWT_AUDIENCE` | Expected token audience | Required |
| `ASAA_AP_JWT_ALGORITHM` | JWT verification algorithm | RS256 |
| `ASAA_AP_SUPPLIER_STATUS_TRANSITIONS_JSON` | Configurable supplier transition map | Starter map in application settings |
| `ASAA_AP_APP_NAME` | API application name | ASAA Finance API |

The upstream identity provider must issue tokens containing `sub`, `org_id`, `iss`, `aud`, `exp` and a `permissions` string array. The application verifies issuer, audience, expiry and signature; do not bypass these checks.

## 8. API areas

- Supplier/AP: `/api/v1/suppliers` and related supplier status endpoints.
- AR: `/api/v1/ar/customers`, `/api/v1/ar/invoices`, `/api/v1/ar/receipts`.
- HR: `/api/v1/hr` employee, lifecycle, employment, documents, assets, leave and exit-case routes.
- Onboarding/offboarding: `/api/v1/onboarding` templates, assignments and tasks.
- Payroll: `/api/v1/payroll` compensation, periods, runs, entries and decisions.
- Master data: `/api/v1/master-data` domain ownership, record references, duplicate candidates and supersession.\n- Governance: `/api/v1/governance` decisions and authority delegations.

The running OpenAPI document is the definitive route/schema reference for the current source revision.

## 9. Development rules

- Work on the explicitly authorized branch; do not modify other branches by assumption.
- Organization default branch names are `main`, `dev`, `new`, `fix`, `test`; branch protection and merge flow remain repository-governed.
- Keep module technology choices local; do not impose a platform-wide stack.
- Reuse shared identity, permission, database and audit services where appropriate.
- Add migrations and tests with schema or workflow changes.
- Never weaken authorization to make tests pass; use explicit test principals and permissions.
- Keep secrets and local databases out of source control.
- Preserve existing project requirements and code boundaries.
- Update these consolidated documents when product scope or architecture changes; avoid creating new standalone Markdown status files.
- Report Built, Built Not Tested, Passed, Blocked and Deferred distinctly.


## 10. Web portal

The responsive ASAA portal lives in `apps/portal` and is an installable Progressive Web App (PWA) for desktop, tablet and mobile browsers. It uses React and Vite as a module-level UI choice. From the repository root:

```bash
cd apps/portal
npm install
npm run dev
npm run build
npm run preview
```

The portal consumes the API using a bearer token from the configured upstream identity provider. The current connection screen accepts a development/session token and keeps it in memory only; it is cleared on reload or sign-out and is not written to local storage, IndexedDB or service-worker caches. Production single sign-on, MFA, refresh-token handling and identity-provider redirect must be configured before production access.

Set `VITE_API_BASE_URL` to the API origin at build time. Configure API `ASAA_AP_CORS_ORIGINS` as a JSON array of exact trusted portal origins, for example `["https://app.example.com"]`. Do not use wildcard origins. The API remains the authorization authority: visible workspace titles do not grant permissions. The initial Founder/CEO/Director designation is a workspace profile label; effective actions depend on verified token permission claims.

The PWA service worker caches only the application shell and same-origin static assets. API paths and cross-origin API requests are not cached. This supports installability and shell launch, not offline access to financial or personal records.

The portal currently surfaces supplier/customer/invoice/receipt, timesheet and expense API records where the session has the relevant read permissions. Missing permissions or unavailable API areas are reported as unavailable; they are not silently treated as empty authoritative business data.
