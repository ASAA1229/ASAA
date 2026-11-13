# Operations Guide

**Status:** Operational design and release checklist. Production deployment is not currently established by this repository.

## 1. Current operational footprint

The current runnable service is the FastAPI API in `apps/ap-api`. It supports local SQLite and has a PostgreSQL 16 integration-test workflow using psycopg 3, the full Alembic chain and PostgreSQL-specific API persistence checks. Production PostgreSQL provisioning, TLS configuration, backup/restore validation, production load/concurrency testing and deployment remain unverified. There is no verified production deployment, configured identity provider, production monitoring stack or validated production backup/restore process evidenced by this branch.

Do not treat a successful local run or CI result as production readiness.

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
