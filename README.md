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

The current executable slice is an API-first Python service in `apps/ap-api`. It contains:

- Accounts Payable supplier foundation.
- Accounts Receivable customer, invoice and receipt foundation.
- HR employee records, lifecycle, employment history, leave requests, document metadata and asset tracking.
- Versioned onboarding/offboarding templates, assignments and task workflows.
- Restricted compensation records and controlled payroll input/review/approval/closure workflows.
- Master-data domain ownership, stewardship, source provenance, duplicate-candidate flagging and non-destructive supersession.
- Governance decision register and time-bounded authority delegation workflow with independent review, revocation and audit.
- Initial TMS timesheet capture, submission and independent review workflows.
- Initial expense claim capture, submission, independent review and separate reimbursement recording.

These are foundational capabilities, not a complete enterprise release or production-ready payroll/finance system. The GAP-024 baseline previously passed source compilation, 37 API tests and SQLite migration upgrade/downgrade/upgrade checks. GAP-002 now adds decision/delegation routes and tests; its CI validation is pending. TMS and expense API foundations are newly added and require CI validation. PostgreSQL runtime integration, real identity-provider integration, UI, production operations and organization-specific policy/UAT remain open.

## Run the current API locally

Requirements: Python 3.11 or newer.

```bash
cd apps/ap-api
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# Linux/macOS:
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m alembic upgrade head
uvicorn asaa_ap.main:app --reload
```

The default local database is SQLite at `apps/ap-api/asaa_ap.db`. The API fails closed for authenticated routes until the RS256 identity settings are configured. Set `ASAA_AP_DATABASE_URL`, `ASAA_AP_JWT_PUBLIC_KEY`, `ASAA_AP_JWT_ISSUER` and `ASAA_AP_JWT_AUDIENCE` in the environment or a local, untracked `.env` file. Never commit private keys, tokens or production secrets. See [Development](docs/DEVELOPMENT.md), [Security](docs/SECURITY.md) and [Operations](docs/OPERATIONS.md).

Run checks from `apps/ap-api`:

```bash
python -m compileall -q src tests
python -m pytest -q
python -m alembic upgrade head
```

API documentation is exposed by FastAPI when the service is running (typically `/docs`).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — domain boundaries, shared services, technical decisions and project preservation.
- [Requirements](docs/REQUIREMENTS.md) — consolidated capability scope, priorities, user needs, acceptance principles and implementation status.
- [Development](docs/DEVELOPMENT.md) — local setup, configuration, commands, tests and contribution workflow.
- [Operations](docs/OPERATIONS.md) — deployment gates, monitoring, backup, recovery and operational runbooks.
- [Security](docs/SECURITY.md) — identity, authorization, data protection, audit and security acceptance requirements.

## Repository and branch

Repository: [ASAA1229/ASAA](https://github.com/ASAA1229/ASAA)

Organization-wide default branch names are `main`, `dev`, `new`, `fix` and `test`. Their exact merge, protection and release rules remain governed by approved repository policy. Work in this change is limited to branch `new`.
