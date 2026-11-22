# ASAA Release Readiness

**Current decision:** NO-GO  
**Authoritative evidence and gap states:** [Project Status](PROJECT_STATUS.md).

## 1. Release decision meanings

- **GO:** all mandatory release gates passed with evidence and required owner approvals.
- **CONDITIONAL GO:** only explicitly approved non-critical limitations remain; no security, legal, privacy, data-integrity or recoverability control is weakened.
- **NO-GO:** any mandatory P0 gate is open, critical defect remains, or evidence/approval is missing.

## 2. Mandatory P0 gates

| Gate | Required evidence | Current state |
|---|---|---|
| Production database | PostgreSQL target provisioned; TLS verified; restricted runtime role; separate migration identity; preflight and migration rehearsal pass | BLOCKED BY EXTERNAL DEPENDENCY (local PostgreSQL 18 migration/integration verified) |
| Identity and SSO/MFA | Approved provider/tenant; tested OIDC sign-in, token validation, MFA, logout, expiry and key rotation | BLOCKED BY EXTERNAL DEPENDENCY (token-validation negative tests pass locally) |
| Identity lifecycle | Joiner/mover/leaver provisioning, revocation, retries and reconciliation | PARTIALLY COMPLETE (adapter, mock provider and reconciliation verified locally; real provider adapter pending) |
| Authorization/security | Tenant/record/field isolation, privileged access, SoD, payroll confidentiality and audit assurance independently tested | PARTIALLY COMPLETE (negative tests pass locally; independent review pending) |
| Backup and recovery | Approved RPO/RTO/retention; automated encrypted backups; restore and integrity exercise | PARTIALLY COMPLETE (tooling and local round trip verified; objectives, schedule and off-site storage pending) |
| Business workflow acceptance | Approved policies, authority matrix and signed UAT for every enabled first-release workflow | BLOCKED BY EXTERNAL DEPENDENCY |
| Critical defects | No unresolved critical security, privacy, data-loss or financial-integrity defect | NEEDS TESTING (no known open critical defect; no independent testing) |

## 3. P1 launch-scope gates

Before a capability is enabled for production, it must have:
- Complete end-to-end business workflow and exception paths.
- API, database and UI/E2E regression evidence.
- Accessibility and supported browser/device verification.
- Performance and concurrency evidence appropriate to its workload.
- Monitoring, alerting, runbook and operational owner.
- Documented user-facing boundaries for deferred or disabled capabilities.

A P1 capability may be excluded from the first release only when it is disabled or clearly unavailable and the owner accepts the reduced scope. Do not expose a preview UI as an operational service.

## 4. Delivery and operational gates

- Reviewed commit and pull request with required checks.
- Reproducible dependency installation and successful build.
- Security/dependency scan reviewed; release artifact has checksum and provenance.
- Environment-specific secrets and least-privilege identities configured.
- Migration, backup and deployment rehearsal completed.
- Smoke tests and rollback/forward-recovery procedure demonstrated.
- Logs, metrics, traces, alert routing, incident owner and escalation active.
- Support ownership, release notes and post-release validation plan recorded.

Jenkins, Nexus and production deployment are not considered verified until actual jobs/agents, publishing/retrieval and environment execution are evidenced.

## 5. Current decision

**NO-GO for production as of 2026-11-13.** API quality and PostgreSQL 16 integration CI passed at commit `ba87df7fdb967adf80d00b7b4771a823708b7582`. Web CI, including four OIDC endpoint transport-policy regression tests and the Vite production build, passed at commit `69e08b2b591cc570d0af0eb4d8121cb32989b00c` ([run 43419337233](https://github.com/ASAA1229/ASAA/actions/runs/43419337233)). Production database provisioning, SSO/MFA provider activation, identity lifecycle, full security assurance, backup/restore, business UAT and operational controls remain open.

Re-evaluate this decision only from the current [Project Status](PROJECT_STATUS.md) gap register and recorded evidence. Do not infer GO from a passing build or CI suite.

## 6. Update 2026-11-13

**Decision remains NO-GO.** The engineering increment closed the locally achievable parts of the gap register (see [Project Status](PROJECT_STATUS.md) section 7): lockfile/lint/audit tooling, UI and accessibility tests, negative security tests, identity provisioning adapter with mock provider, observability and hardening, backup/restore and load/smoke tooling. Local results: API 125 passed (PostgreSQL enabled) / 123 passed, 2 skipped (without), UI 17, Node 4, lint clean, build and audits clean. The new and changed GitHub workflows have not yet run, so no new CI VERIFIED claim is made. Every remaining P0 gate depends on an external decision, environment or independent review listed in [Operations](OPERATIONS.md) section 11.

## 7. Update 2026-11-14 (second follow-up)

Decision remains **NO-GO**. Additional locally verified items: SCIM adapter (fake server), encrypted/rotated/scheduled backups with staleness check, alert rules and log schema, provisional PostgreSQL performance gate, cross-browser and mobile reflow E2E. Explicitly not run: the container deployment rehearsal (Docker daemon unavailable) and promtool (CI only). All new workflows are unexecuted on GitHub.


## Update 2026-11-14 (documentation owner)

Head `a40c7ca` has a failing lint (`playwright.config.js` parse error) and removed accessibility CSS; the earlier green lint, E2E and accessibility evidence is for `ac2f696`. Decision unchanged: NO-GO. No GitHub Actions run observed.


## Update 2026-11-15

The a40c7ca regression was repaired in 37f478d; coordinator-verified there: lint, build, 17 UI tests, pytest SQLite 165 passed / 6 skipped. Rehearsal 13/13 and promtool passed locally (agent-reported). Head `0dbb67b` carries new workspaces and registers that are agent-pushed and not yet coordinator-verified. No GitHub Actions run observed. Decision unchanged: **NO-GO**.


## Release gate reassessment — 2026-11-20

**Decision: NO-GO.** Current `new` branch API quality, Web CI, and PostgreSQL integration workflow runs passed (run IDs 44732168373, 44732168216, and 44732168210). The observed API-quality and PostgreSQL-integration runs on both `dev` and `main` failed. Treat every result as specific to its recorded workflow run and commit.

The following mandatory release gates remain open: production database and hosting readiness; real identity-provider/SSO/MFA activation; complete identity lifecycle and tenant/record/field authorization assurance; independent security review; owner-approved backup/restore RPO/RTO and recovery exercise; business workflow UAT; production monitoring/alert routing and named operational ownership; and successful exact-SHA CI on the release candidate.

Do not promote branches or deploy based solely on the green `new` runs. Follow the organization promotion policy and require the applicable PR review and checks. Historical local test results in earlier sections are not substitutes for current CI or production acceptance evidence.
