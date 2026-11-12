# ASAA Accounts Receivable API — Initial Foundation

The Accounts Receivable (AR) slice is implemented inside the existing finance API package and reuses the AP database engine, SQLAlchemy metadata, JWT principal verification, permission dependency and audit-event table.

## Scope implemented

- Organization-scoped customer account registration and lookup, with duplicate detection.
- Draft customer invoices with itemized lines, explicit currency, dates, amounts and caller-supplied tax amounts.
- Version-checked draft invoice editing; issued invoices are immutable through this endpoint.
- Later allocation of previously unapplied receipt balances to eligible invoices, with customer/currency/outstanding checks.
- Server-side line, subtotal, tax and invoice-total calculations using decimal arithmetic.
- Explicit invoice issue action with version check and permission.
- Record customer receipts without initiating or claiming an external money transfer.
- Allocate receipts to one or more invoices, including partial settlement and unapplied amounts.
- Outstanding balance and payment-state calculation.
- Organization scoping and append-only application audit events.

## API routes

- `POST/GET /api/v1/ar/customers`
- `GET /api/v1/ar/customers/{customer_id}`
- `POST/GET /api/v1/ar/invoices`
- `PUT /api/v1/ar/invoices/{invoice_id}` (draft only)
- `GET /api/v1/ar/invoices/{invoice_id}`
- `POST /api/v1/ar/invoices/{invoice_id}/issue`
- `POST/GET /api/v1/ar/receipts`
- `POST /api/v1/ar/receipts/{receipt_id}/allocations`

## Permissions

- `ar:customer:read`, `ar:customer:write`
- `ar:invoice:read`, `ar:invoice:write`, `ar:invoice:issue`
- `ar:receipt:read`, `ar:receipt:write`, `ar:receipt:allocate`
- `audit:read` remains shared with AP.

The application identity provider must issue these claims. No default production user or permission bypass is provided.

## Financial and policy boundaries

- Currency is a caller-selected three-letter code; no base currency or FX conversion is assumed.
- Tax amounts are explicit invoice inputs. No tax rate, tax jurisdiction, withholding, statutory invoice numbering or e-invoicing policy is inferred.
- Invoice numbers are optional, supplied by the authorized caller and unique within the organization when present.
- Receipts are internal records of reported/confirmed receipt evidence. The API does not initiate bank transfers or claim to verify bank settlement.
- Partial allocations are supported. Unapplied receipt balances can be allocated later through a controlled endpoint. Reversal, refunds, credit notes and bank reconciliation remain later work.
- Invoices can be edited only while Draft, using optimistic version checks. Approval chains, disputes and write-offs remain future work.
- Customer records are a minimal AR customer master; full CRM/contact/contract integration is not yet implemented.

## Local setup

Use the existing instructions in the parent `apps/ap-api/README.md`. Run Alembic migrations before starting the API. Tests are in `apps/ap-api/tests/test_ar.py`.

## Verification status

Source, migration and automated test cases have been added. Test execution and live PostgreSQL/identity-provider integration have not yet been independently verified in this environment. Do not treat this slice as production-ready until the test suite, database migration, security review and finance user acceptance checks pass.
