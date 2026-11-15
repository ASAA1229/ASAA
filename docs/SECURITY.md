# Security Requirements and Controls

**Status:** Security baseline; formal risk assessment and production review remain required.

## 1. Security objectives

Protect organizational, employee, customer, financial, project and operational information. Prevent unauthorized access, disclosure, alteration and execution. Ensure sensitive actions are attributable, reviewable and recoverable.

Apply least privilege, defense in depth, secure defaults, privacy by design and separation of duties.

## 2. Identity and authentication

- Use an approved identity provider; do not create implicit production identities or bypass authentication.
- Validate JWT signature using the configured RS256 public key, issuer, audience and expiry.
- Require the expected subject and organization identity claims; permissions must be an explicit string array.
- Use secure key distribution, rotation, revocation and emergency response.
- Require MFA for privileged and sensitive access according to approved policy.
- Separate human users, service accounts and automation identities.
- Support session expiry, revocation and access lifecycle integration before production use.
- Fail closed when identity configuration is missing or invalid.

Current API settings include `ASAA_AP_JWT_PUBLIC_KEY`, `ASAA_AP_JWT_ISSUER`, `ASAA_AP_JWT_AUDIENCE` and `ASAA_AP_JWT_ALGORITHM` (RS256 default).

## 3. Authorization and data isolation

- Enforce authorization server-side on every read, write, decision, export and administrative operation.
- Derive organization scope from the verified principal, never trust a caller-supplied organization ID as authority.
- Enforce organization scoping in database queries and mutations.
- Use separate permissions for read, create/update, lifecycle transitions, approval, closure, export and administration.
- Apply record-level and field-level restrictions for salary, payroll, employee documents, identity data, customer and financial records.
- General HR or manager access must not imply compensation/payroll access.
- Do not grant approval authority from job title or department membership alone.
- Audit access grants, changes, privileged actions and sensitive decisions.
- Test cross-organization access denial and horizontal/vertical privilege escalation.

## 4. Separation of duties and workflow security

- Separate maker and checker for sensitive leave, compensation and payroll decisions where implemented.
- Prevent self-approval for protected decisions.
- Require reasons for sensitive lifecycle and status changes.
- Use explicit state-transition graphs; reject invalid transitions.
- Use optimistic version checks for mutable records where supported.
- Require authorized approval before high-impact external writes, payments, deployments or automation.
- Keep rejection, return-for-correction, cancellation and exception paths auditable.
- Emergency access must be time-limited, scoped, justified and reviewed.

## 5. Data classification and privacy

Establish a data classification catalogue before production. At minimum, identify public, internal, confidential and restricted data and map each field/document to its handling rules.

- Minimize collection and retention.
- Restrict employee, identity, salary, bank, legal, health and disciplinary information to explicitly authorized roles.
- Do not put secrets or sensitive personal information in free-form notes, evidence references, logs or payroll breakdown fields.
- Encrypt data in transit and at rest using approved infrastructure controls.
- Define data residency, retention, legal hold, correction, export and lawful deletion rules.
- Separate real data from demo/test data.
- Ensure reports and AI features respect source permissions and data boundaries.
- Do not use personal or confidential data for model training without an approved legal and privacy basis.

## 6. Secrets and integration security

- Never commit passwords, tokens, private keys, signing secrets, connection strings or production credentials.
- Use an approved secret manager or protected deployment environment.
- Request minimum provider scopes; use separate credentials per environment and integration.
- Support credential rotation, revocation, expiry and health monitoring.
- Validate webhook signatures and event authenticity before processing.
- Use TLS and secure service-to-service authentication.
- Do not execute untrusted repository content or instructions found in external data.
- Sanitize logs and error responses to avoid leaking secrets or sensitive records.

## 7. Audit and accountability

Audit important reads of restricted records where policy requires and all sensitive mutations/decisions. Record actor/service identity, timestamp, organization scope, action, target, outcome, reason and correlation reference. Capture before/after values only where necessary and lawful.

Application audit events are not yet proven immutable at the database/infrastructure layer. Production requires restricted database privileges, tamper-evident/immutable retention where required, monitoring of audit-write failures and protected access to audit records.

## 8. Application and API security

- Validate all input with typed schemas and strict bounds.
- Use parameterized ORM/database access; avoid unsafe dynamic SQL.
- Apply request size, pagination, rate limiting and resource limits.
- Protect against injection, broken access control, mass assignment, insecure direct object references, replay and race conditions.
- Use version checks/idempotency for operations that may be retried.
- Return generic errors to clients; keep detailed diagnostics in protected logs.
- Maintain dependencies, scan for vulnerabilities and patch on a defined cadence.
- Keep API docs/debug endpoints disabled or protected in production.
- Use secure CORS, trusted-host, proxy and transport settings once deployment topology is selected.

## 9. AI and automation security

- Treat repository files, external documents, webhooks and user-generated content as untrusted data, not executable instructions.
- Restrict AI retrieval to records the requesting user can access.
- Label generated content and inferred conclusions.
- Do not allow AI to approve payroll, make legal determinations, change permissions, transfer money, deploy software or mutate repositories without a separately approved capability and explicit human authorization.
- Require scoped targets, permission checks, dry-run/impact preview, idempotency, audit and recovery controls for write automation.
- Provide stop/revoke controls and human review for high-impact actions.

## 10. Current implementation controls and limitations

Current API foundation includes verified-principal authorization, organization-scoped records, dedicated permissions, separate HR/payroll access, maker-checker checks for selected leave/compensation/payroll decisions, explicit lifecycle transitions, version checks in selected workflows and application audit events.

Not yet established: real identity provider and MFA, production key management, database-level audit immutability, PostgreSQL security configuration, document binary storage and retention, centralized security monitoring, penetration testing, vulnerability scanning policy, formal threat model, privacy impact assessment and production incident exercises.

## 11. Master-data registry security notes

- Domain and record references are organization-scoped and use separate read/write/supersession permissions.
- Duplicate matching accepts only a keyed pseudonymous fingerprint generated by trusted code; API responses do not return the fingerprint.
- A duplicate match is a review candidate, not proof of identity. Human review is required before supersession.
- Supersession preserves the original reference and records the canonical link and reason; no automatic merge or destructive deletion occurs.
- The registry stores source references and ownership metadata, not the underlying employee, supplier, customer or asset payloads.

## 12. Security acceptance gates

Before production:
1. Approve threat model, data classification, privacy impact and jurisdictional obligations.
2. Validate authentication, issuer/audience/signature/expiry and key rotation.
3. Test organization isolation and every permission boundary, including negative tests.
4. Verify maker-checker and privileged-access workflows.
5. Complete dependency, static, dynamic and penetration testing appropriate to exposure.
6. Configure encryption, secrets, database privileges, audit protection and log redaction.
7. Validate backup confidentiality, restore access and incident response.
8. Review document, notification, identity and external integration scopes.
9. Assign security ownership, vulnerability remediation SLAs and incident escalation.
10. Record approval evidence and residual risks before release.


## 13. Decision and delegation register security notes

- Decision and delegation records are organization-scoped and protected by separate read/create/review/revoke permissions.
- Delegations require a finite effective window, independent approval and a reason. The creator, delegator and delegate cannot review their own delegation request.
- Decision proposals name the intended decision-maker; only that subject can approve or reject, and the proposal creator cannot self-approve.
- Rejections and revocations require reasons; state transitions use expected versions and are audited.
- A registered delegation does not alter JWT permissions or grant application access. Authorization remains controlled by the existing verified-principal permission checks until a separately approved identity/policy integration is implemented.
- Subject identifiers and scope/action codes are references, not verified employment roles or proof of authority outside this register.


## 14. OIDC, signing-key rotation and MFA assurance

- The portal uses Authorization Code + PKCE (S256), state validation and a public SPA client; no client secret is shipped to the browser.
- Access tokens remain in memory. Session storage contains only transient PKCE transaction state/verifier and is cleared during callback processing.
- The API accepts RS256 only. Configure either an HTTPS JWKS endpoint (ASAA_AP_JWT_JWKS_URL) or a static public key fallback. JWKS retrieval is cached to support signing-key rotation.
- Issuer, audience, signature and expiry remain mandatory. ASAA_AP_REQUIRED_ACR and ASAA_AP_REQUIRED_AMR can enforce provider-specific authentication assurance/method claims.
- MFA must be required by the identity provider's policy; an application UI label or user role does not prove MFA.
- The access token must carry the organization and permission claims expected by the API. Provider claim mapping must be reviewed and tested.
- Do not treat a Retain/Modify/Revoke access-review decision as an actual provider entitlement change. Automated provisioning, deprovisioning, session revocation, refresh and logout require a separately implemented provider adapter and verified provider APIs.
- Real SSO/MFA is not operationally accepted until a provider, tenant, public client, API audience, JWKS endpoint, redirect URIs, MFA policy and lifecycle integration are selected and tested.


## 15. Role and access assignment governance

- Role templates accept explicit permission identifiers only; wildcard permissions are rejected.
- Role template activation and subject access assignment approval require independent reviewers and reasons.
- Assignment approval is scoped and effective-dated; revocation is reasoned and audited.
- These records are not an authorization engine. They do not add or remove JWT claims, create provider accounts, disable sessions or revoke provider grants.
- Production authorization requires an approved provider adapter to map active approved assignments into token claims, enforce scope, expire/revoke grants and reconcile provider state. Until then, API authorization continues to trust only validated JWT permission claims and verified organization scope.


## 16. First-release security verification backlog (2026-11-13)

Current code provides security foundations, but production assurance is not complete. The following evidence is required before real employee, customer, payroll or financial data is introduced.

### Identity and session assurance
- [ ] Select and configure the production identity provider, tenant, public client, issuer, audience, JWKS and exact redirect/logout URIs.
- [ ] Test PKCE/state handling and issuer, audience, signature, expiry, key rotation and invalid/missing-claim rejection.
- [ ] Enforce MFA at the provider; test compliant and non-compliant assurance/method claims.
- [ ] Test logout, session expiry, refresh/revocation, account disablement, recovery and signing-key rollover.
- [ ] Implement provider lifecycle synchronization and prove joiner/mover/leaver access changes, reconciliation and failure recovery.

### Authorization and sensitive data
- [ ] Inventory every API route and UI action with required permission, organization scope, record scope and field sensitivity.
- [ ] Test unauthenticated, insufficient-permission, cross-organization, cross-record and horizontal/vertical privilege-escalation cases.
- [ ] Verify HR directory access cannot reveal restricted compensation, payroll, employee documents or other confidential fields.
- [ ] Verify maker/checker, no-self-approval, delegation expiry/revocation and access-review decisions at the enforcement boundary.
- [ ] Test exports, search, reporting, attachments and error paths against the same authorization rules as record APIs.

### Platform, audit and privacy
- [ ] Verify production database TLS, encryption, runtime/migration role separation and least privilege against the provisioned target.
- [ ] Verify audit events capture actor, organization, action, target, outcome, timestamp and correlation; alert on write failure.
- [ ] Restrict audit mutation/deletion and configure tamper-evident or immutable retention where required.
- [ ] Complete data classification, minimization, retention/deletion, residency and privacy/jurisdiction review.
- [ ] Complete dependency and static analysis, dynamic/API security tests and independent penetration testing appropriate to deployment exposure.
- [ ] Validate rate limits, request bounds, CORS/trusted hosts, security headers, secret handling and production error/log redaction.
- [ ] Record vulnerabilities, remediation, retest evidence and owner-approved residual risks.

No production security approval is implied by the presence of these checklist items. Attach test reports, configuration evidence, revision and review approval before marking each item complete.


## Security status and assurance evidence

The current security gap state and verification evidence are tracked in [Project Status](PROJECT_STATUS.md), especially ASAA-002 through ASAA-006. This document defines required controls; it does not certify that the controls have passed production review. Release decisions follow [Release Readiness](RELEASE_READINESS.md).


## 17. Security verification evidence (2026-11-13, local)

Evidence is from the local environment only (SQLite and a disposable PostgreSQL 18); it is not independent assurance and not production approval.

| Control | Evidence | Result |
|---|---|---|
| Authentication fails closed | `test_unauthenticated_and_malformed_credentials_are_rejected_on_every_route`, `test_all_routes_fail_closed_when_identity_is_unconfigured`, `test_non_rs256_configuration_is_refused` | Forged (alg none, foreign key), wrong issuer/audience, expired, missing `sub`/`org_id`, malformed permissions: 401; unconfigured identity: 503 on every API operation. |
| Server-side permission enforcement | `test_every_api_route_denies_a_principal_with_no_permissions` (route inventory from the OpenAPI document; > 90 operations) | Every `/api/` operation returns 403 for a principal with no permissions, regardless of organization. |
| Organization isolation / IDOR | `test_cross_organization_record_isolation`, `test_valid_token_works_and_org_comes_only_from_the_token` | Another organization's employee, supplier, customer, compensation, audit and leave records return 404/empty; caller-supplied organization parameters/headers have no effect. |
| Field/role separation for payroll | `test_hr_access_does_not_reveal_compensation_or_payroll`, `test_write_permission_does_not_imply_approval_or_read` | HR read/write does not expose compensation data or payroll endpoints; compensation write does not imply read or approval; maker cannot approve own record. |
| Mass assignment / injection | `test_mass_assignment_and_unknown_fields_are_rejected`, `test_injection_strings_are_treated_as_data` | Unknown fields (organization_id, status, created_by) rejected with 422; SQL metacharacters stored as data. |
| Audit | `test_privileged_actions_write_attributable_audit_events`, `test_rejected_privileged_action_does_not_create_success_audit_or_change_state` | Events carry actor, correlation ID and timestamp, are organization-scoped, require `audit:read`, and contain no compensation amounts; rejected actions leave no success event. |
| Audit-write failure behavior | `test_failed_audit_write_leaves_no_partial_state` | Fail closed: if the audit insert fails the business change is rolled back, the client receives a generic 500, and service recovers when the audit store is healthy again. |
| Logging and error redaction | `tests/test_observability.py` | Bearer tokens, JWTs, e-mail addresses, URL passwords, `token=`/`password=` pairs and sensitive keys are redacted; stack frames are not logged; readiness failures do not leak connection detail. |
| HTTP hardening | `test_security_headers_and_no_store_on_api_responses`, `test_oversized_request_bodies_are_rejected_with_413`, `test_api_docs_are_disabled_in_production_mode` | `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, restrictive CSP, `Cache-Control: no-store` on API responses, 1 MiB body limit, OpenAPI/docs disabled in production. `/metrics` is hidden in production unless a token is configured. |
| Identity lifecycle | `tests/test_identity_sync.py` | Revocation (disable, session revoke, entitlement clear) is idempotent; stale leaver jobs do not lock out re-hired staff; dead-letter jobs alert and are audited; identity-sync permissions are separated (repair needs enqueue and reconcile) and organization-isolated; the in-memory provider is refused in production. |
| Dependency vulnerabilities | `npm audit --audit-level=high` = 0; `pip-audit` = none known | Also automated in CI (not yet run on GitHub for the new jobs). |

**Findings.** The new negative API tests found no authorization defect in the existing API. Defects found elsewhere: portal crash for partially-permitted sessions (fixed), portal reporting an active connection after 401 (fixed), a vulnerable test-framework dependency chain (replaced), `package-lock.json` untracked (fixed), OpenAPI/docs exposed in production mode and no security headers/body limit (fixed).

**Not done (still required by section 12):** threat model, data classification, penetration test, independent review, database-level audit immutability, rate limiting, real identity provider and MFA verification, production key management, privacy impact assessment.

### 17.1 Update 2026-11-14: database privileges and session verification

| Control | Evidence | Result |
|---|---|---|
| Migration/runtime role separation | `scripts/db_roles.py provision`, `tests/test_db_privileges.py` (local PostgreSQL 18) | Runtime role: not superuser/createdb/createrole/replication/bypassrls; no schema CREATE; owns no tables; DML only; `alembic_version` SELECT-only; `audit_events` SELECT/INSERT only; CREATE/DROP/ALTER/TRUNCATE refused; attempts executed and refused inside rolled-back transactions; migrations by the runtime role fail while the migration role succeeds. |
| Checker is not vacuous | `test_checker_detects_an_over_privileged_role` | The owner/admin role fails the check. |
| Application works with least privilege | `test_application_works_end_to_end_as_the_runtime_role_and_audit_rows_are_append_only` | Reads, creates and audit inserts succeed under the runtime role with zero errors; `UPDATE audit_events` is refused. |
| Session verification | `test_whoami_requires_a_valid_token_and_returns_only_verified_claims`, Playwright invalid-token test | `/api/v1/me` needs only a valid token and returns verified claims; the portal no longer treats an arbitrary string as a connected session. |
| E2E credentials hygiene | `apps/ap-api/scripts/e2e_api.py` | Fresh RSA key and 30-minute tokens per run, written only to the git-ignored `.e2e/`; the previously committed token file was untracked (it was expired, issuer `e2e.invalid`, signed by a discarded key). |

Still open: the production role matrix is an owner/DBA decision (the policy above is the repository baseline); the grants must be re-run after each migration (`provision` is idempotent); this is local evidence, not a review of any production database.

### 17.2 Update 2026-11-14 (second follow-up): provisioning, backups and delivery artifacts

| Control | Evidence | Result |
|---|---|---|
| SCIM adapter transport and secrets | `tests/test_scim_provider.py` | HTTPS required for non-localhost endpoints; bearer token only from configuration; 401/403 are permanent (not retried); filter values escaped; 429/5xx back off with bounded retries; no personal data in errors. |
| Encrypted backups | `tests/test_backup_restore.py` | AES-256-GCM with authenticated frames (index + final flag): bit flips, reordered frames, truncation and wrong key rejected; key from environment/file, must decode to 32 bytes; unencrypted source removed after encryption. Key custody and rotation remain deployment decisions. |
| Backup monitoring | `check-staleness` | Exit code 2 for no backup, failed latest run, stale or missing artifact. |
| Container image | `apps/ap-api/Dockerfile` | Non-root user, no secrets baked in, healthcheck; not built or scanned locally (Docker daemon not running). |
| Alerting | `monitoring/asaa-alerts.yml` | Authentication-denial spike and 5xx alerts defined; routing/ownership not configured. |

Limitations unchanged: no independent review, no provider/MFA activation, no vendor-specific SCIM validation, no image vulnerability scan, rate limiting still absent.


## 18. Update 2026-11-15 (agent-pushed, pending coordinator verification where marked)

- Notification outbox minimizes sensitive content in message templates and respects preferences (commit a16459d, tested locally).
- Governed registers carry per-register permissions, maker-checker review, audit events and organization isolation (commit 3bda274; agent-pushed, pending verification).
- The reports API aggregates per currency and per permission and never exposes payroll or salary data; the audit events endpoint gains action/actor/entity/outcome filters (commit 0dbb67b; agent-pushed, pending verification).
- The a40c7ca accessibility regression was repaired in 37f478d (coordinator-verified lint, build, UI tests, pytest). Independent security review is still pending; no GitHub Actions run observed.
