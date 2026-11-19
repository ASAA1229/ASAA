# ASAA Engineering Maturity and Delivery Roadmap

**Status:** Prioritized delivery sequence; no calendar commitments implied.  
**Authoritative progress:** [Project Status](PROJECT_STATUS.md).  
**Acceptance backlog:** [User Stories](USER_STORIES.md).

## Delivery principles

Preserve the existing modular API and React/Vite client. Prefer small, testable vertical slices. Do not infer policy, legal, tax, approval or banking rules. No production deployment, main-branch merge, force-push or history rewrite without explicit authorization.

## P0 — Safe enterprise foundation

### Epic P0-A: Production data integrity
- Provision production PostgreSQL 16+ with TLS, separate migration/runtime identities and least privilege.
- Run production preflight and migration rehearsal.
- Define transaction, concurrency, idempotency and reconciliation requirements for sensitive finance/HR operations.
- Approve backup objectives, automate backups and prove restore/integrity.
**Dependencies:** hosting, database/network access, credentials, RPO/RTO and retention decisions.
**Exit:** production DB preflight, migration evidence, restore evidence and owner approval.

### Epic P0-B: Identity, authorization and governance
- Select and configure the approved OIDC provider/tenant.
- Verify Authorization Code + PKCE, token validation, MFA assurance, logout, expiry and signing-key rotation.
- Implement identity lifecycle provisioning/deprovisioning and drift reconciliation.
- Independently verify organization/record/field authorization, privileged access, SoD and audit controls.
**Dependencies:** provider/tenant decision, user/employee mapping, approved role and authority matrix.
**Exit:** end-to-end identity lifecycle evidence and security acceptance.

### Epic P0-C: First-release business acceptance
- Define the exact launch scope and named business owners.
- Validate organization hierarchy, authority/delegation and access review.
- Complete scripted HR, leave, payroll, AP/procurement and AR/expense UAT within approved policies.
- Disable or exclude unaccepted workflows from the release.
**Dependencies:** approved policies, jurisdiction and business owner availability.
**Exit:** signed UAT, defects dispositioned, no critical data/security issues.

## P1 — Operational completeness and quality

### Epic P1-A: Complete finance and procurement
- Complete procure-to-pay: sourcing/quotes, purchase orders, receipt, invoice matching, duplicate prevention, payment authorization and settlement reconciliation.
- Complete receivables adjustments, allocations, ageing, disputes/refunds and bank reconciliation as approved.
- Strengthen accounting traceability, reconciliation and exception workflows.
**Exit:** accepted end-to-end finance scenarios and reconciliation evidence.

### Epic P1-B: Complete workforce and payroll
- Close HR lifecycle, onboarding/offboarding, leave, assets and employment-history edge cases.
- Complete payroll calculation inputs, validation, maker-checker, reconciliation, approval and controlled closure.
- Integrate identity changes with employment lifecycle.
**Exit:** payroll and HR UAT with restricted-access and SoD verification.

### Epic P1-C: Test engineering and accessibility
- Add frontend unit/component tests, UI and E2E regression for launch scope.
- Add keyboard, screen-reader, contrast and responsive validation.
- Add supported browser/device matrix and compatibility evidence.
- Establish performance budgets, load and concurrency tests.
**Exit:** quality gates pass at a recorded release candidate.

### Epic P1-D: DevOps and operational reliability
- Lock frontend dependencies and use reproducible installs.
- Add dependency/security scanning, SBOM, checksums and artifact provenance.
- Define deployment approvals, environment promotion, smoke tests and rollback.
- Add structured logs, metrics, traces, alert routing, runbooks and incident ownership.
- Verify Jenkins/Nexus only if actual integrations are selected and accessible.
**Exit:** non-production deployment and recovery rehearsal with evidence.

### Epic P1-E: Branch and change governance
- Establish ASAA branches: main, dev, new, fix, test.
- Review existing divergence before any branch synchronization.
- Configure protection/rulesets and required checks where repository permissions allow.
- Require review, tests and traceable release notes.
**Exit:** tested PR workflow; no unapproved merge into main.

## P2 — Enterprise expansion

After the first stable release, prioritize by approved business demand:
- CRM, sales, customer and contract lifecycle.
- Project, product, portfolio and engineering management.
- Service delivery, support, SLA and client operations.
- Inventory, assets, facilities and logistics.
- Legal, risk and compliance expansion.
- Knowledge, collaboration, reporting and analytics.
- Permission-aware AI assistance and controlled automation.

## Sequence and dependencies

1. P0-A database and recovery foundations.
2. P0-B identity, authorization and governance (parallelize only where dependencies permit).
3. P0-C business scope and UAT.
4. P1-A/P1-B workflow completion.
5. P1-C quality, P1-D operational reliability and P1-E change governance.
6. P2 expansion.

A phase can progress only when its exit criteria have evidence. Current status and exact blockers are maintained only in [Project Status](PROJECT_STATUS.md).


---

## ASAA Master Requirements Baseline v1.0 — 2026-11-14

Approved planning/governance reference for the four ASAA projects and shared ecosystem capabilities. Round 6 consolidation is complete at framework level. Individual requirement mapping, full source reconciliation, branch/runtime verification, named owners, dependency validation, acceptance criteria, evidence-based gaps and delivery estimates remain pending. Approval does not authorize implementation, testing, deployment, paid services or merges.

See `docs/ASAA_MASTER_REQUIREMENTS_BASELINE.md`, `docs/PROJECT_SCOPE.md` and `docs/EPIC_STATUS.md` for the current project scope and epic tracker.


## Baseline alignment — 2026-11-14

This roadmap is subordinate to the approved ASAA Master Requirements Baseline v1.0. Round 6 consolidation is complete at framework level; detailed requirement population, applicability, ownership, dependencies, evidence-based gap scoring and delivery estimates remain pending. Use the epic register and project scope document added in this branch. Do not infer completion from plans or source presence. No implementation, test, deployment, paid service, merge or release authorization is granted by baseline approval.


---

## Discovery reconciliation work — 2026-11-19

Next planning sequence (not a delivery commitment):
1. Reconcile Sets 1–12 answers against the approved Master Requirements Baseline v1.0.
2. Map applicable requirements to existing epics/sub-epics/features/stories/tasks and identify duplicates, conflicts and omissions.
3. Verify repository/source/test/CI/integration/runtime evidence for every existing status; retain unknowns as NOT ASSESSED.
4. Assign accountable owners, dependencies, measurable acceptance criteria and evidence expectations.
5. Prioritize and estimate only after scope and dependencies are validated; prepare a proposed roadmap for approval.
6. Keep implementation, testing, deployment and release behind separate explicit authorization gates.
