# ASAA Finance API — AP and AR foundations

API-first finance service. AP supplier management and the initial AR customer, invoice and receipt workflows share one API package and security/database foundation. This is a module-specific technology choice, not a mandatory ASAA-wide stack.

## Technology

- Python 3.11+
- FastAPI and Pydantic v2
- SQLAlchemy 2 and Alembic
- PostgreSQL via psycopg 3
- PyJWT with RS256 public-key verification
- pytest and HTTPX

## Local setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[test]"
```

For local SQLite development, the API uses a local SQLite file by default. Configure `ASAA_AP_DATABASE_URL` to a PostgreSQL connection string for shared environments, and set `ASAA_AP_JWT_PUBLIC_KEY`, `ASAA_AP_JWT_ISSUER`, and `ASAA_AP_JWT_AUDIENCE`. The API deliberately fails closed when identity verification is not configured. An upstream approved identity provider must issue RS256 tokens containing `sub`, `org_id`, `iss`, `aud`, `exp`, and a `permissions` string array.

```bash
alembic upgrade head
uvicorn asaa_ap.main:app --reload
pytest
```

## Supplier permissions

- `supplier:read` — list and read suppliers / duplicate candidates.
- `supplier:write` — create and edit supplier profiles.
- `supplier:status` — request status transitions.
- `supplier:verify` — additionally required to activate a supplier.
- `audit:read` — read organization-scoped audit events.

All records are organization-scoped from the verified token claim. The API has no delete endpoint. Updates require `expected_version`; status changes are separate commands with a reason and a defined transition graph. Creation starts in `Draft`. The initial status-transition map is a configurable starter default; override it with `ASAA_AP_SUPPLIER_STATUS_TRANSITIONS_JSON` rather than treating it as a fixed ASAA policy.

## Scope boundaries

This slice does not implement purchase requests, quotations, purchase orders, goods receipts, invoices, invoice matching, payments, bank details, bank integration, tax rules, accounting posting or supplier bank-account maintenance. Those remain later AP phases. Registration references are opaque optional identifiers; no jurisdiction-specific tax or company-registration policy is assumed.

## Current limitations

- Identity provider, key distribution, role/permission claim issuance and production secret management remain integration decisions.
- No UI is included in this API-first vertical slice.
- Audit events are append-only through this application interface; database-level immutability/retention controls require infrastructure policy.
- PostgreSQL migration is supplied; automated tests use isolated SQLite databases.

## Accounts Receivable permissions

- `ar:customer:read`, `ar:customer:write`
- `ar:invoice:read`, `ar:invoice:write`, `ar:invoice:issue`
- `ar:receipt:read`, `ar:receipt:write`, `ar:receipt:allocate`

Draft invoice editing and unapplied receipt allocation are included in the current AR slice. See [AR Initial Implementation Status](../../docs/AR_INITIAL_IMPLEMENTATION_STATUS.md) for scope, safeguards and outstanding work.
