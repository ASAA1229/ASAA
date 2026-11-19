# ASAA — Enterprise Operating Platform

ASAA is the planned internal operating platform for the organization being established. It is intended to connect governance, people, projects, products, engineering, service delivery, customers, sales, finance, procurement, operations, compliance, knowledge and organizational intelligence in one permissioned environment.

ASAA is not limited to HR, ERP, CRM, project management or software development. It is designed around ASAA's own operating model rather than as a generic multi-company SaaS product.

## Product principles

- **Configurable and technology-independent:** each domain selects appropriate technologies; no organization-wide language, framework, database or cloud is mandated.
- **One connected operating environment:** domain modules own their records and expose documented contracts; shared services provide identity, authorization, workflow, audit, reference data and integration capabilities.
- **Suitable for an early-stage organization:** planned capabilities do not imply that the company is already incorporated, that every department is staffed, or that policies and approval authorities have been approved.
- **Secure by default:** least privilege, organization and record scoping, separation of duties, traceable decisions and human approval for sensitive actions.
- **Evidence-led:** planned, implemented, tested and operationally verified are different states.
- **Project independence:** connected projects retain their own repositories, requirements, technology choices and delivery workflows.

## Current repository implementation

The current executable slice includes a responsive React/Vite web client at the repository root (`src/`, `public/`) and an API-first Python service in `apps/ap-api`. The web client exposes connected supplier lifecycle, purchase-request, customer/invoice/receipt, timesheet, expense, HR and payroll workflows. HR includes employee directory/profile, employment lifecycle, onboarding/offboarding and leave request/review views. Payroll includes restricted compensation, periods/runs, supplied entries, reconciliation and maker-checker review/closure. Other module workspaces remain staged previews until their APIs and workflows are integrated. The API contains:

- Accounts Payable supplier foundation and initial purchase-request workflow (draft, submit, independent review).
- Accounts Receivable customer, invoice and receipt foundation.
- HR employee records, lifecycle, employment history, leave requests, document metadata and asset tracking.
- Versioned onboarding/offboarding templates, assignments and task workflows.
- Restricted compensation records and controlled payroll input/review/approval/closure workflows.
- Master-data domain ownership, stewardship, source provenance, duplicate-candidate flagging and non-destructive supersession.
- Governance decision register and time-bounded authority delegation workflow with independent review, revocation and audit.
- Organization profile and configurable hierarchy administration with maker-checker activation, plus dated access-review campaigns and independently recorded recertification decisions.
- Governed role/permission templates and scoped access assignment requests with independent approval and revocation records; these remain policy records until identity-provider synchronization is configured.
- Generic OIDC Authorization Code + PKCE sign-in plumbing, RS256 JWKS verification and configurable MFA assurance-claim enforcement hooks; provider activation remains pending selection and configuration.
- Initial TMS timesheet capture, submission and independent review workflows.
- Initial expense claim capture, submission, independent review and separate reimbursement recording.

These are foundational capabilities, not a complete enterprise release or production-ready payroll/finance system. PostgreSQL 16 migration and API integration checks pass in CI. The repository includes a production PostgreSQL preflight command (`apps/ap-api/scripts/validate_postgresql.py`), but production database provisioning/TLS, backup/restore, capacity validation and operational readiness remain open. Provider-specific SSO/MFA activation, automated identity provisioning/deprovisioning and organization-specific policy/UAT also remain open.

## Local development — start both services

Requirements: Node.js 22 or newer, npm, and Python 3.11 or newer.

From the repository root, install the frontend dependencies and prepare the API's isolated Python environment:

```powershell
npm install
npm run setup:api
```

The API setup command creates `apps/ap-api/.venv` and installs the API plus test dependencies. Then start both services together:

```powershell
npm run dev
```

This single command starts:

- Web UI: `http://localhost:5173`
- FastAPI: `http://127.0.0.1:8001`
- Interactive API docs: `http://127.0.0.1:8001/docs`

Press **Ctrl+C** once to stop both services.

### Run services separately when needed

Run either command from the repository root:

```powershell
npm run dev:web
npm run dev:api
```

The API command uses the project's `.venv` when it exists. If the API environment has not been prepared, run `npm run setup:api` first.

### Database and authentication setup

The default local database is SQLite at `apps/ap-api/asaa_ap.db`. Production mode (ASAA_AP_ENVIRONMENT=production) requires PostgreSQL. PostgreSQL 16 migration and API integration validation runs in `.github/workflows/postgres-integration.yml`. Before first API use, run the migration from the API directory:

```powershell
cd apps/ap-api
.venv\\Scripts\\python.exe -m alembic upgrade head
```

For Linux/macOS, use `.venv/bin/python -m alembic upgrade head` instead.

The API fails closed for authenticated routes until the RS256 identity settings are configured. Set `ASAA_AP_DATABASE_URL`, `ASAA_AP_JWT_PUBLIC_KEY`, `ASAA_AP_JWT_ISSUER` and `ASAA_AP_JWT_AUDIENCE` in the environment or a local, untracked `.env` file. Never commit private keys, tokens or production secrets. The default CORS configuration permits the local frontend origins on port 5173.

Run API checks from `apps/ap-api` using the virtual environment's Python:

```powershell
.venv\\Scripts\\python.exe -m compileall -q src tests
.venv\\Scripts\\python.exe -m pytest -q
```

For Linux/macOS, replace the executable path with `.venv/bin/python`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — domain boundaries, shared services, technical decisions and project preservation.
- [Requirements](docs/REQUIREMENTS.md) — consolidated capability scope, priorities, user needs, acceptance principles and implementation status.
- [Development](docs/DEVELOPMENT.md) — local setup, configuration, commands, tests and contribution workflow.
- [Operations](docs/OPERATIONS.md) — deployment gates, monitoring, backup, recovery and operational runbooks.
- [Security](docs/SECURITY.md) — identity, authorization, data protection, audit and security acceptance requirements.

## Applications

- `src/` and `public/` — responsive installable React/Vite web client for desktop, tablet and mobile.
- `apps/ap-api` — FastAPI business API for finance, people, governance and workforce workflows.
- `scripts/` — cross-platform local development and API environment helpers.

The web client is a connected operational slice for selected finance and workforce workflows, plus a navigable preview of the wider platform. It is not yet a complete ERP or production release. Production remote access requires a deployed HTTPS frontend/API, configured identity provider and trusted CORS origins.

## Repository and branch

Repository: [ASAA1229/ASAA](https://github.com/ASAA1229/ASAA)

Organization-wide default branch names are `main`, `dev`, `new`, `fix` and `test`. Their exact merge, protection and release rules remain governed by approved repository policy. Work in this change is limited to branch `new`.


## First-release status (2026-11-13)

**Production release status: NO-GO.** The current branch contains a substantial executable slice, and PostgreSQL 16 migration/API integration checks pass in CI. Production database provisioning and preflight, provider-specific SSO/MFA activation, automated identity lifecycle, full security assurance, backup/restore, monitoring, deployment rehearsal and business UAT are not yet evidenced. Do not use this repository with real employee/payroll/financial data in production until the mandatory gates in [User Stories](docs/USER_STORIES.md), [Operations](docs/OPERATIONS.md) and [Security](docs/SECURITY.md) are passed and approved.

The first release should be limited to a coherent set of validated governance, workforce and finance workflows. Recruitment, CRM, portfolio/project/product management, service delivery, inventory/facilities, advanced analytics and AI remain expansion scope unless explicitly brought into the approved launch scope. Preview workspaces must not be represented as operational modules.


## Project status and release controls

The single authoritative maturity assessment, current gap register and verified progress record is [Project Status](docs/PROJECT_STATUS.md). Use [POC](docs/POC.md) for the current executable scope, [Roadmap](docs/ROADMAP.md) for delivery sequence, [Testing](docs/TESTING.md) for test evidence, [DevOps](docs/DEVOPS.md) for CI/CD controls and [Release Readiness](docs/RELEASE_READINESS.md) for GO/NO-GO gates.

**Current release decision: NO-GO.** API quality and PostgreSQL 16 CI integration passed at commit `ba87df7`; web CI passed at commit `69e08b2`, including four OIDC endpoint transport-policy regression tests and a Vite production build ([run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233)). These results do not establish production database, identity-provider, backup/recovery, full security-assurance or business-acceptance readiness.
