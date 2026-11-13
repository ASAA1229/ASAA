# Development Guide

## 1. Repository layout

```text
ASAA/
├── public/                 # static files and PWA assets
├── src/                    # React application source and UI assets
├── index.html
├── package.json
├── vite.config.js
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
- SQLite for lightweight local development; PostgreSQL 16 is the integration-test and intended shared/production database engine.
- PostgreSQL 16 service/container for local database integration testing.
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
- `0011_timesheets_expenses`
- `0012_purchase_requests`
- `0013_org_access_admin`
- `0014_org_unit_review`
- `0015_authorization_roles`

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

SQLite CI does not replace PostgreSQL integration tests. The separate postgres-integration workflow starts PostgreSQL 16, applies all 15 migrations, runs the complete API suite plus PostgreSQL-specific people/payroll persistence checks, and verifies downgrade/re-upgrade on the disposable CI database. Latest passing evidence: [PostgreSQL integration CI 43407390790](https://github.com/ASAA1229/ASAA/actions/runs/43407390790) and [API quality CI 43407390884](https://github.com/ASAA1229/ASAA/actions/runs/43407390884).

## 7. Configuration reference

| Variable | Purpose | Default / requirement |
|---|---|---|
| `ASAA_AP_DATABASE_URL` | SQLAlchemy database URL | Local SQLite default; PostgreSQL postgresql+psycopg URL for shared/production |
| `ASAA_AP_ENVIRONMENT` | Runtime environment | development; production requires PostgreSQL |
| `ASAA_AP_DB_POOL_SIZE` | PostgreSQL persistent connection pool size | 5 |
| `ASAA_AP_DB_MAX_OVERFLOW` | Maximum overflow connections | 10 |
| `ASAA_AP_DB_POOL_TIMEOUT_SECONDS` | Wait for a pooled connection | 30 seconds |
| `ASAA_AP_DB_POOL_RECYCLE_SECONDS` | Recycle pooled connections | 1800 seconds |
| `ASAA_AP_DB_CONNECT_TIMEOUT_SECONDS` | PostgreSQL connection timeout | 5 seconds |
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

The running OpenAPI document is the definitive route/schema reference for the current source revision. /health is a process liveness check; /ready executes SELECT 1 and returns HTTP 503 when the configured database cannot be reached.

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

The responsive ASAA portal lives at the repository root (`src/`, `public/`) and is an installable Progressive Web App (PWA) for desktop, tablet and mobile browsers. It uses React and Vite as a module-level UI choice. From the repository root:

```bash
npm install
npm run dev  # http://localhost:5000
npm run build
npm run preview
```

The portal consumes the API using a bearer token from the configured upstream identity provider. The current connection screen accepts a development/session token and keeps it in memory only; it is cleared on reload or sign-out and is not written to local storage, IndexedDB or service-worker caches. Production single sign-on, MFA, refresh-token handling and identity-provider redirect must be configured before production access.

Set `VITE_API_BASE_URL` to the API origin at build time. Configure API `ASAA_AP_CORS_ORIGINS` as a JSON array of exact trusted portal origins. For local development use `["http://localhost:5000", "http://127.0.0.1:5000"]`; for production use the exact HTTPS portal origin. Do not use wildcard origins. The API remains the authorization authority: visible workspace titles do not grant permissions. The initial Founder/CEO/Director designation is a workspace profile label; effective actions depend on verified token permission claims.

The PWA service worker caches only the application shell and same-origin static assets. API paths and cross-origin API requests are not cached. This supports installability and shell launch, not offline access to financial or personal records.

The portal currently surfaces supplier/customer/invoice/receipt, timesheet, expense, HR and payroll workflows where the session has the relevant read/action permissions. HR includes employee directory/profile, employment lifecycle, onboarding/offboarding, leave and asset views. Payroll includes separately permissioned compensation, periods/runs, entries and maker-checker review. Missing permissions are not treated as grants; dashboard registers are requested only when the corresponding read permission is present.


## 11. Organization administration and SSO configuration

The organization administration endpoints are under /api/v1/administration:
- GET/PUT/PATCH /profile
- GET/POST /units, PATCH /units/{id}, and POST /units/{id}/review
- GET/POST /access-reviews
- POST /access-reviews/items/{id}/decision

Authorization governance endpoints are under /api/v1/authorization:
- GET/POST /roles, PATCH /roles/{id}, POST /roles/{id}/review
- GET/POST /assignments, POST /assignments/{id}/review and POST /assignments/{id}/revoke

Role and assignment permissions are separately controlled by authorization:role:read/write/approve and authorization:assignment:read/create/approve/revoke. Approved templates and assignment records are governance intent only until the identity-provider adapter maps them into signed access-token claims.

Master-data domain and record endpoints remain under /api/v1/master-data. Administration routes require explicit permissions: organization:profile:read/write, organization:structure:read/write, identity:access-review:read/create/review, plus the separate masterdata permissions. Never grant these solely from a job title.

For a selected OIDC provider, configure the frontend build environment:

| Variable | Purpose |
|---|---|
| VITE_OIDC_AUTHORITY | Exact OIDC issuer/authority URL |
| VITE_OIDC_CLIENT_ID | Public SPA client ID; never a client secret |
| VITE_OIDC_REDIRECT_URI | Exact registered redirect URI; defaults to current origin |
| VITE_OIDC_SCOPES | Requested scopes; defaults to openid profile email |

Register the SPA as a public client using Authorization Code + PKCE (S256), exact redirect URIs and provider-supported browser token exchange. Configure provider MFA/conditional-access policy independently. The API access token must be a signed RS256 JWT accepted by the API and contain sub, org_id, iss, aud, exp and a permissions string array. The token issuer and audience must match API settings.

API identity settings:

| Variable | Purpose |
|---|---|
| ASAA_AP_JWT_JWKS_URL | HTTPS JWKS endpoint for signing-key discovery/rotation; preferred for providers |
| ASAA_AP_JWT_PUBLIC_KEY | Static RS256 public key fallback |
| ASAA_AP_JWT_ISSUER | Exact expected issuer |
| ASAA_AP_JWT_AUDIENCE | Expected API audience |
| ASAA_AP_JWT_ALGORITHM | RS256 only |
| ASAA_AP_JWT_LEEWAY_SECONDS | Clock-skew tolerance (default 30) |
| ASAA_AP_REQUIRED_ACR | Optional exact required authentication context |
| ASAA_AP_REQUIRED_AMR | Optional required authentication method value |

The identity provider must issue the configured acr/amr claims if the corresponding requirement is enabled. Do not assume a generic MFA claim name; map to the provider's documented claim semantics. Browser-based code exchange requires provider CORS support for the SPA origin. Access tokens are memory-only; refresh tokens are not persisted or renewed. Provider logout, token revocation, SCIM provisioning/deprovisioning and group synchronization are not implemented. Until a provider is selected and tested, development token connection remains a development-only fallback.

Do not use production identities or real access tokens in automated tests. Use explicit test principals and isolated signing keys.
