# AP Phase 1 — Supplier Foundation Implementation

**Repository:** `ASAA1229/ASAA`  
**Target branch:** `new`  
**Implementation slice:** API-first supplier management foundation  
**Technology policy:** Module-specific selection; no ASAA-wide stack is prescribed.

## Repository baseline

At the start of AP Phase 1, the `new` branch contained planning documents only. AP Phase 1 subsequently established the shared finance API package, database foundation, JWT principal verification, permission dependency, audit-event model, migrations and automated tests. AR now reuses those shared components.

## Technology selection

- Python 3.11+, FastAPI and Pydantic v2
- SQLAlchemy 2 and Alembic
- PostgreSQL for shared environments; SQLite for local/test use
- PyJWT with RS256 public-key verification for upstream identity tokens
- pytest and HTTPX

Supplier master records are structured, relational, organization-scoped and audit-sensitive. PostgreSQL is selected for transactional integrity and constraints. This choice applies to this AP API slice only; other ASAA modules may select different technologies.

## Implemented scope

- Supplier registration, profile retrieval and listing.
- Supplier code, legal/trading names, contacts, website, category, optional opaque registration reference, addresses and notes.
- New suppliers start in `Draft`.
- Normalized legal-name duplicate detection; email and registration-reference candidate matching; database uniqueness for normalized names and supplier codes within the organization.
- Controlled statuses: Draft, Pending Verification, Active, On Hold, Suspended and Archived. Archived is terminal in the configurable starter transition map; the map is overridable through `ASAA_AP_SUPPLIER_STATUS_TRANSITIONS_JSON`. Activation additionally requires `supplier:verify`.
- Controlled profile updates with expected-version checks and optimistic concurrency.
- Organization scope derived from verified identity claims.
- Permission checks: `supplier:read`, `supplier:write`, `supplier:status`, `supplier:verify`, `audit:read`.
- Audit events for supplier creation, profile updates and status changes, written in the same transaction.
- No supplier delete endpoint.
- Alembic initial migration for supplier and audit tables.

## Verification status

| Capability | Build status | Verification status |
|---|---|---|
| Supplier registration and profile API | Built Not Tested | Not independently re-run during the AR change |
| Validation and duplicate detection | Built Not Tested | Not independently re-run during the AR change |
| Status lifecycle and activation permission | Built Not Tested | Not independently re-run during the AR change |
| Controlled updates and optimistic concurrency | Built Not Tested | Not independently re-run during the AR change |
| Organization-level record isolation | Built Not Tested | Not independently re-run during the AR change |
| Permission enforcement | Built Not Tested | Test case exists; not independently re-run during the AR change |
| Supplier audit events | Built Not Tested | Test assertions exist; not independently re-run during the AR change |
| Initial migration | Built Not Tested | Migration source exists; not independently re-applied during the AR change |
| RS256 verification with real identity provider/key set | Built Not Tested | Identity provider/key configuration unavailable |
| PostgreSQL runtime integration | Built Not Tested | No PostgreSQL server/credentials available |
| User interface | Not Started | Not applicable |

Verification note: a prior development note recorded 10 tests and an SQLite migration as passed, but execution logs are not available for independent confirmation in this workspace. Treat the AP suite and migration as Built Not Tested until re-run against the current shared finance code. No production deployment or real identity integration was performed.

## Not included

Purchase requests, quotations, supplier selection, purchase orders, goods/service receipts, supplier invoices, invoice matching, payment scheduling/execution, bank details, bank integrations, tax calculations and accounting postings remain later AP slices. No company, tax, banking, currency, payment or approval policy is inferred.

## Remaining work

1. Select/configure the identity provider, signing-key distribution, issuer/audience and role-to-permission mapping.
2. Run migration and integration tests against the selected PostgreSQL environment.
3. Define supplier verification evidence and configurable verification workflow.
4. Establish database-level audit immutability, retention, backup and privileged-access controls.
5. Add the UI after the ASAA application shell and UX approach are selected.
6. Add document/contract attachments through a shared document service.
7. Validate duplicate matching rules against real supplier data and define an approved exception/merge workflow.

**Release statement:** This is an initial development slice, not a production-ready AP release. Production readiness requires identity integration, PostgreSQL verification, security review, operational controls and owner acceptance.
