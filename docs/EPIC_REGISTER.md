# ASAA Epic Register — 2026-11-14

| ID | Epic | Development | Testing | Integration | Acceptance/release |
|---|---|---|---|---|---|
| ASAA-E01 | Governance and organization administration | Partial (governed registers: 11 register workspaces, audit view; IMPLEMENTED — NOT FULLY TESTED, agent-pushed) | Local API/UI evidence; new registers pending coordinator verification | Cross-project pending | Not accepted |
| ASAA-E02 | Identity/authentication/authorization | Partial | Local security tests; SCIM adapter vs local fake server only | Real provider pending | Provider acceptance pending |
| ASAA-E03 | People and workforce lifecycle | Partial | Local API/UI evidence | Provider lifecycle sync pending (fake SCIM only) | Business UAT pending |
| ASAA-E04 | Payroll, leave, timesheets, expenses | Partial | Local tests/browser evidence | Policy E2E pending | Owner acceptance pending |
| ASAA-E05 | Supplier, procurement and AP | Partial | Local API/UI evidence | External integration pending | Owner acceptance pending |
| ASAA-E06 | AR, customer and commercial | Partial | Local API/UI evidence | Billing integration pending | Owner acceptance pending |
| ASAA-E07 | Project/product/service delivery | Planned / unverified | Not assessed | Not assessed | Not assessed |
| ASAA-E08 | Analytics and reporting | Partial (reports API, financial reporting workspace: IMPLEMENTED — NOT FULLY TESTED, agent-pushed 0dbb67b) | Not coordinator-verified; deferred to test phase | Not assessed | Not accepted |
| ASAA-E09 | Security, privacy, audit | Partial | Local security tests and PostgreSQL 18 DB privilege checks | Independent review pending | Production acceptance pending |
| ASAA-E10 | CI/CD, release and operations | Partial | Coordinator-verified at 37f478d: lint, build, 17 UI tests, pytest SQLite 165 passed/6 skipped; Playwright 96 passed/3 skipped (agent-reported); promtool passed (agent-reported); no GitHub run observed | Docker rehearsal 13/13 locally (agent-reported); no hosting target (deferred to deployment phase) | Release NO-GO |
| ASAA-E11 | Backup, recovery, continuity | Partial | Local encrypted backup/restore tests; PostgreSQL round trip | Production exercise pending | RPO/RTO approval pending |
| ASAA-E12 | Shared ecosystem/data integration | Planned / partial | Not assessed | Contracts pending | Not accepted |

Repository status snapshot remains NO-GO for production. Keep development, testing, integration, acceptance and release separate.

**Reconciled 2026-11-14 (documentation owner):** development, testing, integration and acceptance columns updated to the verified evidence in PROJECT_STATUS.md. Local evidence is not CI evidence (no GitHub Actions run observed; `gh` unauthenticated) and nothing here is CI VERIFIED.

**Reconciled 2026-11-15 (documentation owner):** development, testing, integration and acceptance columns updated to the verified evidence in PROJECT_STATUS.md. Local evidence is not CI evidence (no GitHub Actions run observed; `gh` unauthenticated) and nothing here is CI VERIFIED.
