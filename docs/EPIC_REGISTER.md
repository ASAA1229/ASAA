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


---

## Discovery expansion — Sets 7–12 (2026-11-19)

The questionnaire phase is closed at Set 12. The user selected “all of the above” for every question in Sets 1–12. These selections are **candidate requirements for reconciliation**, not evidence of implementation, a committed delivery promise, or a change to Master Requirements Baseline v1.0.

New cross-cutting candidate requirement domains to map into the existing epic hierarchy:
- Shared architecture, bounded project ownership, API/event contracts, service identities, common directory, configuration and secrets, notifications, documents, search, workflow, audit, observability, reporting and shared AI services.
- Data architecture, domain ownership, master/reference data, validation, synchronization, consistency, privacy, classification, retention/deletion, import/export, migration, lineage, analytics, offline handling and AI data governance.
- Security governance, identity/authentication/authorization, privileged access, application/API/network/device/repository security, secure SDLC, supply-chain controls, encryption, monitoring, vulnerability/incident response, third-party controls and AI/JARVIS safeguards.
- CI/CD, build/test automation, artifact provenance, environment promotion, IaC, deployment strategies, rollback, infrastructure/platform cost controls, multi-platform support and pipeline observability.
- Quality engineering across requirements, acceptance criteria, unit/integration/API/UI/E2E/regression/performance/security/accessibility/compatibility/mobile/desktop/data/AI testing, test data, defects, release gates and UAT.

Reconciliation rules:
1. Preserve all existing epic IDs, evidence, status distinctions and repository-specific architecture.
2. Map applicable candidate requirements to Project → Epic → Sub-epic → Feature → User Story → Tasks → Acceptance Criteria → Dependencies → Status → Evidence.
3. Do not mark a capability implemented, tested, integrated, accepted or released from questionnaire selections alone.
4. Keep PLANNED / NOT ASSESSED / IMPLEMENTED-NEEDS-TESTING / TESTED / INTEGRATED / ACCEPTED / RELEASED distinctions explicit.
5. The approved Master Requirements Baseline v1.0 remains unchanged; any new baseline requires separate approval.
6. Planning/documentation only. No code, tests, deployment, merge, paid service, production change or release is authorized by this update.


Project epic coverage: ASAA-E01–E12. Apply the candidate domains as cross-cutting sub-epics/features where applicable; do not create duplicate epics or change existing development/testing/integration/acceptance values without new evidence.


## Owner decision alignment — 2026-11-27

The following requirement scope is confirmed. Existing epic IDs and implementation evidence remain unchanged; map these requirements into the corresponding existing epics rather than creating duplicate epics.

- **ASAA-E02 Identity and access:** centralized cross-project identity; local login plus optional SSO; HR-driven joiner/mover/leaver lifecycle; immediate revocation and audit.
- **ASAA-E03 People and workforce:** five-day week, annual 12-holiday calendar, two sick days/month, nine-hour shifts including one-hour lunch, two-month probation, quarterly reviews, 15-day default notice, owner-decided salary and recruitment authority.
- **ASAA-E04 Payroll, leave and expenses:** owner-controlled compensation decisions; approved overtime with case-by-case owner compensation; configurable jurisdiction and employee-category rules.
- **ASAA-E05 Supplier, procurement and AP / ASAA-E06 AR and finance:** complete local/dummy workflows and real-provider adapters built but disabled; strict dummy/real separation; explicit owner activation and transaction safeguards.
- **ASAA-E09 Security and audit:** MFA, role controls, immutable audit trail, transaction limits, duplicate prevention, anomaly detection, emergency disable/lockout and encrypted backup/recovery requirements.
- **ASAA-E10 CI/CD and operations:** local-first operation and ₹0 cost; Jenkins in use; paid Nexus intentionally paused.
- **ASAA-E12 Shared ecosystem/data integration:** hybrid centralized data architecture and centralized identity APIs.

No branch promotion, paid integration activation, production release or implementation status change is implied by this requirements update.
