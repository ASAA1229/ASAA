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
| Production database | PostgreSQL target provisioned; TLS verified; restricted runtime role; separate migration identity; preflight and migration rehearsal pass | NEEDS TESTING |
| Identity and SSO/MFA | Approved provider/tenant; tested OIDC sign-in, token validation, MFA, logout, expiry and key rotation | OWNER ACCEPTANCE PENDING |
| Identity lifecycle | Joiner/mover/leaver provisioning, revocation, retries and reconciliation | NOT STARTED |
| Authorization/security | Tenant/record/field isolation, privileged access, SoD, payroll confidentiality and audit assurance independently tested | NEEDS TESTING |
| Backup and recovery | Approved RPO/RTO/retention; automated encrypted backups; restore and integrity exercise | NOT STARTED |
| Business workflow acceptance | Approved policies, authority matrix and signed UAT for every enabled first-release workflow | OWNER ACCEPTANCE PENDING |
| Critical defects | No unresolved critical security, privacy, data-loss or financial-integrity defect | NEEDS TESTING |

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

**NO-GO for production as of 2026-11-13.** PostgreSQL 16 integration and API quality CI passed at commit `ba87df7fdb967adf80d00b7b4771a823708b7582`. Production database, SSO/MFA provider activation, identity lifecycle, security assurance, backup/restore, business UAT and operational controls remain open.

Re-evaluate this decision only from the current [Project Status](PROJECT_STATUS.md) gap register and recorded evidence. Do not infer GO from a passing build or CI suite.
