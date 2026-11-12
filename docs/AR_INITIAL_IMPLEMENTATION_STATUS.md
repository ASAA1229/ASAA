# AR Initial Implementation Status

**Repository:** ASAA1229/ASAA  
**Branch:** new  
**Scope:** Initial Accounts Receivable API foundation

## Status summary

| Capability | Status | Evidence / boundary |
|---|---|---|
| Customer master registration and lookup | Built Not Tested | Organization-scoped customer endpoints; duplicate checks |
| Draft invoice creation | Built Not Tested | Itemized lines, decimal calculations and caller-supplied tax amounts |
| Draft invoice editing | Built Not Tested | Version-checked replacement of dates, notes and lines; Draft-only |
| Invoice issue action | Built Not Tested | Permission-gated, version-checked transition |
| Receipt recording | Built Not Tested | Records receipt evidence; does not initiate transfers |
| Receipt allocation | Built Not Tested | Initial allocation plus later unapplied-balance allocation; partial payments and over-allocation checks |
| Outstanding balances | Built Not Tested | Calculated from recorded allocations |
| Permissions and audit | Built Not Tested | Reuses shared JWT principal, permission dependency and audit_events |
| Database migration | Built Not Tested | Alembic revision 0002_ar_foundation |
| Automated tests | Built Not Tested | Test cases added; not executed in this environment |
| PostgreSQL integration | Not Started / Not Tested | No configured database connection verified |
| Identity-provider integration | Not Tested | Requires upstream RS256 issuer and permission claims |

## Financial control decisions deliberately not assumed

- No tax rates, statutory rules, jurisdiction, invoice-numbering sequence or e-invoicing rules.
- No company base currency, FX rate source or conversion logic.
- No automatic payment collection, bank API, bank verification or settlement assertion.
- Receipt records are not equivalent to bank reconciliation.
- No approval authority, credit limits, customer terms or write-off rules have been invented.

## Remaining AR work

1. Configurable invoice approval workflow; draft editing is now implemented.
2. Contract, order, project and milestone linkage.
3. Invoice delivery, reminders and customer communications.
4. Unapplied receipt reallocation is implemented; reversal and refund handling remain open.
5. Receipt reversal, refunds, credit/debit notes and disputes.
6. Bank statement import, matching and reconciliation.
7. Aging reports, customer statements, dashboards and finance exports.
8. Customer master synchronization with CRM.
9. Concurrency, security and PostgreSQL integration testing.
10. Business-user acceptance and operational controls.

## Verification rule

The current source is classified as **Built Not Tested**. Do not mark any AR capability Passed until the test suite and migration are executed successfully against an isolated test database, PostgreSQL integration is verified, and organization-specific finance acceptance criteria are approved.
