# Operations Guide

**Status:** Operational design and release checklist. Production deployment is not currently established by this repository.

## 1. Current operational footprint

The current runnable service is the FastAPI API in `apps/ap-api`. It supports local SQLite and has a PostgreSQL 16 integration-test workflow using psycopg 3, all 15 Alembic migrations and PostgreSQL-specific API persistence checks. The latest passing PostgreSQL integration run is [43407390790](https://github.com/ASAA1229/ASAA/actions/runs/43407390790); API quality checks passed at [43407390884](https://github.com/ASAA1229/ASAA/actions/runs/43407390884). Production PostgreSQL provisioning, TLS configuration, backup/restore validation, production load/concurrency testing and deployment remain unverified. There is no verified production deployment, configured identity provider, production monitoring stack or validated production backup/restore process evidenced by this branch.

Do not treat a successful local run or CI result as production readiness.

### Production PostgreSQL validation command

After provisioning the target database and setting the production environment variables, run from `apps/ap-api` with the restricted application runtime role:

```bash
ASAA_AP_ENVIRONMENT=production python scripts/validate_postgresql.py
```

The command checks PostgreSQL 16+, TLS on the active connection, least-privilege application role attributes, no runtime schema/table ownership or schema CREATE privilege, Alembic head alignment, revision-column capacity, required application tables and SELECT/INSERT/UPDATE privileges. It redacts the database URL and returns a non-zero exit code if a check fails. Run migrations with a separate migration-only identity before running this check. This command has not been run against a provisioned production database in this project.

## 2. Environment configuration

Each environment must supply its own:
- Database URL and network/TLS settings.
- RS256 JWT public key, issuer and audience.
- Secret-management and key-rotation mechanism.
- Logging/monitoring destinations.
- Document, notification and other provider settings when integrated.

Use separate credentials and databases for development, test, staging and production. Do not copy production records into development unless an approved, minimized and protected test-data process exists.

## 3. Deployment readiness checklist

Before first production deployment:
1. Confirm legal entity, operating jurisdictions, data residency and applicable obligations.
2. Approve the production architecture, hosting provider, network boundaries and environment ownership.
3. Provision PostgreSQL with TLS certificate verification, least-privilege database roles, encryption at rest, connection limits and monitored storage. Configure ASAA_AP_ENVIRONMENT=production and a postgresql+psycopg URL; production mode rejects SQLite.
4. Configure the approved identity provider, RS256 key distribution/rotation, issuer/audience, MFA policy and permission claims.
5. Complete migration rehearsal and backup on a production-like database.
6. Complete security/privacy review, dependency review, access-control tests and concurrency/load tests.
7. Configure centralized structured logs, metrics, traces, alert routing and incident ownership.
8. Define document storage, retention, notification and integration providers before enabling those workflows.
9. Validate backup restoration and disaster recovery against approved recovery objectives.
10. Complete business UAT for finance, HR and payroll workflows; approve policies and delegated authority.
11. Establish release approvals, rollback plan, change window and post-deployment smoke tests.
12. Document support ownership and escalation.

## 4. Release procedure

For each release:
1. Identify the exact commit, branch and release scope.
2. Review code changes, migration changes, dependency changes and security impact.
3. Run compilation, full automated tests and migration checks.
4. Run PostgreSQL integration tests against the target major version.
5. Back up the target database and verify backup completion.
6. Apply migrations through a controlled deployment job using a migration-only credential.
7. Deploy the application artifact built from the reviewed commit.
8. Run health checks and authorized smoke tests.
9. Verify logs, error rates, database connectivity and critical workflows.
10. Record release revision, migration revision, approvals, test evidence and outcome.

Do not apply destructive schema changes without a staged expand/migrate/contract plan and verified recovery route. Prefer forward fixes over unreviewed production downgrades.

## 5. Monitoring and alerting requirements

Production operations should monitor:
- Process health, startup failures, request rate, latency and error rate.
- Authentication failures, invalid tokens, permission denials and suspicious access patterns.
- Database availability, connection pool pressure, query latency, locks, storage and migration state.
- API exceptions, dependency health and resource utilization.
- Audit event write failures and gaps.
- Integration connection status, last successful sync, retries, rate limits and stale data.
- Payroll/finance workflow exceptions and unreconciled records, without exposing sensitive payloads.
- Backup age, backup failures, restore-test age and storage capacity.

Alerts need severity, owner, acknowledgement, runbook and escalation. Avoid logging tokens, passwords, private keys, bank details, full employee documents or unnecessary personal data.

## 6. Backup and recovery requirements

Before production use, define and approve RPO, RTO, retention, encryption, geographic/residency constraints and restore ownership. The actual values are not yet specified.

Required controls:
- Automated database backups and point-in-time recovery where supported.
- Encrypted backups with access separated from application credentials.
- Document/object storage backup and metadata consistency, once binary storage is integrated.
- Backup success/failure monitoring and retention enforcement.
- Regular restore exercises in an isolated environment.
- Recovery runbooks for database loss, credential compromise, application rollback and provider outage.
- Reconciliation checks after recovery to detect missing or duplicate finance/workforce events.

A backup is not considered valid until a restore has been demonstrated and recorded.

## 7. Incident response

For a suspected security or availability incident:
1. Record detection time, affected service/environment and reporter.
2. Preserve relevant logs and audit evidence without copying secrets into tickets.
3. Classify severity and notify the designated incident owner.
4. Contain compromised credentials or integrations through approved revocation/rotation.
5. Protect data integrity; suspend affected write workflows if necessary.
6. Recover through the approved runbook and verify critical data/workflows.
7. Assess privacy/legal notification obligations with authorized owners.
8. Record root cause, impact, corrective actions and follow-up verification.

No incident commander, SLA or notification authority is assumed until assigned.

## 8. Data and workflow operations

- Keep migrations versioned and forward-only in production unless rollback has been explicitly tested and approved.
- Monitor pending approvals, stale workflows, failed integrations and unclosed exceptions after those features are implemented.
- Reconcile financial records with their authoritative external sources; receipt records do not prove bank settlement.
- Never run statutory payroll or tax calculations until applicable policies/rules are approved and tested.
- Ensure access revocation is coordinated across identity, application, document and device providers when integrations exist.
- Review privileged access, service accounts, signing keys and database credentials periodically.
- Preserve audit history and retention according to approved policy.

## 9. Current operational gaps

Not yet evidenced as implemented: production hosting/deployment automation, production PostgreSQL provisioning/TLS and load validation, automated backup and restore, disaster-recovery exercises, centralized monitoring/alerting, log retention, incident response ownership, production secrets management, document storage operations, notification delivery operations, integration health dashboards and support SLAs. PostgreSQL 16 migration and API integration checks run in CI, but do not constitute production validation.

These are production release gates, not optional documentation tasks.


## 10. First-release execution checklist (baseline: 2026-11-13)

This checklist converts the documented operational gaps into release tasks. Current status is not started or blocked unless explicit evidence is attached; do not mark a task complete because a runbook or script exists.

### Environment and database
- [ ] Approve hosting provider/region, network topology, data residency and environment owners.
- [ ] Provision isolated development, staging and production environments; configure HTTPS and trusted origins.
- [ ] Provision PostgreSQL 16+ with encryption at rest and certificate-verified TLS.
- [ ] Create separate migration/runtime roles and prove least privilege on the target database.
- [ ] Configure pool limits, timeouts, storage/capacity alerts and production secret delivery/rotation.
- [ ] Rehearse all migrations from the supported starting revision on a production-like copy.
- [ ] Run `ASAA_AP_ENVIRONMENT=production python scripts/validate_postgresql.py` against the actual target using the runtime role; retain redacted output.
- [ ] Run load, concurrency, connection saturation and failure-recovery tests; record thresholds and results.

### Identity and access lifecycle
- [ ] Select provider and record tenant, issuer, audience, public client, redirect/logout URIs and JWKS endpoint.
- [ ] Configure PKCE, issuer/audience/signature/expiry validation and signing-key rotation.
- [ ] Enforce MFA at the provider and test required assurance/method claims.
- [ ] Validate login/logout, session expiry, refresh/revocation, account disablement and recovery.
- [ ] Implement and test joiner/mover/leaver provisioning, role/scope synchronization and reconciliation.
- [ ] Verify revoked/expired access is removed within an owner-approved service target, including active sessions.

### Observability, security and recovery
- [ ] Centralize structured logs, metrics, traces and health checks; redact tokens, secrets and restricted personal/financial data.
- [ ] Assign alert severity, on-call owner, runbook, acknowledgement and escalation for service, database, audit, identity, integration and backup failures.
- [ ] Define and approve RPO, RTO, retention, backup encryption and recovery ownership.
- [ ] Enable automated backups/PITR where supported and alert on missed/failed backups.
- [ ] Restore database and document metadata into an isolated environment; record integrity checks and measured recovery time.
- [ ] Establish incident response, vulnerability remediation, credential/key rotation and audit-retention procedures.

### Delivery and business acceptance
- [ ] Automate reviewed build, test, migration and deployment stages with approval gates and migration-only credentials.
- [ ] Record artifact/commit, migration revision, approvals and release notes for every deployment.
- [ ] Exercise smoke tests, rollback/forward recovery and post-deployment verification.
- [ ] Name business owners and approve role matrix, authority limits, HR/leave, payroll, expense, procurement, retention and jurisdiction-specific policies.
- [ ] Complete scripted UAT for every included workflow using synthetic or approved minimized data.
- [ ] Resolve release-blocking defects and record business, security and operations sign-off.

### Operational release decision

Production deployment is **NO-GO** while any mandatory P0 task is unchecked, unless a formally approved exception is documented and does not compromise security, legal obligations, data integrity or recoverability. The current PostgreSQL CI run is useful evidence for migration/API compatibility only; it does not close the production database checklist.
