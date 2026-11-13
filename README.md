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

The current executable slice includes a responsive React/Vite web client at the repository root (`src/`, `public/`) and an API-first Python service in `apps/ap-api`. The web client now exposes connected supplier lifecycle, purchase-request, customer/invoice/receipt, timesheet and expense workflows. Other module workspaces remain staged previews until their APIs and workflows are integrated. The API contains:

- Accounts Payable supplier foundation and initial purchase-request workflow (draft, submit, independent review).
- Accounts Receivable customer, invoice and receipt foundation.
- HR employee records, lifecycle, employment history, leave requests, document metadata and asset tracking.
- Versioned onboarding/offboarding templates, assignments and task workflows.
- Restricted compensation records and controlled payroll input/review/approval/closure workflows.
- Master-data domain ownership, stewardship, source provenance, duplicate-candidate flagging and non-destructive supersession.
- Governance decision register and time-bounded authority delegation workflow with independent review, revocation and audit.
- Organization profile and configurable hierarchy administration, plus dated access-review campaigns and independently recorded recertification decisions.
- Generic OIDC Authorization Code + PKCE sign-in plumbing, RS256 JWKS verification and configurable MFA assurance-claim enforcement hooks; provider activation remains pending selection and configuration.
- Initial TMS timesheet capture, submission and independent review workflows.
- Initial expense claim capture, submission, independent review and separate reimbursement recording.

These are foundational capabilities, not a complete enterprise release or production-ready payroll/finance system. PostgreSQL runtime integration, provider-specific SSO/MFA activation, automated identity provisioning/deprovisioning, production operations and organization-specific policy/UAT remain open.

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

- Web UI: `http://localhost:5000`
- FastAPI: `http://127.0.0.1:8000`
- Interactive API docs: `http://127.0.0.1:8000/docs`

Press **Ctrl+C** once to stop both services.

### Run services separately when needed

Run either command from the repository root:

```powershell
npm run dev:web
npm run dev:api
```

The API command uses the project's `.venv` when it exists. If the API environment has not been prepared, run `npm run setup:api` first.

### Database and authentication setup

The default local database is SQLite at `apps/ap-api/asaa_ap.db`. Before first API use, run the migration from the API directory:

```powershell
cd apps/ap-api
.venv\\Scripts\\python.exe -m alembic upgrade head
```

For Linux/macOS, use `.venv/bin/python -m alembic upgrade head` instead.

The API fails closed for authenticated routes until the RS256 identity settings are configured. Set `ASAA_AP_DATABASE_URL`, `ASAA_AP_JWT_PUBLIC_KEY`, `ASAA_AP_JWT_ISSUER` and `ASAA_AP_JWT_AUDIENCE` in the environment or a local, untracked `.env` file. Never commit private keys, tokens or production secrets. The default CORS configuration permits the local frontend origins on port 5000.

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
