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
