# ASAA Enterprise Operating Platform — Proof of Concept

**Status:** Executable foundational slice; not a production-ready enterprise release  
**Baseline:** See [authoritative Project Status](PROJECT_STATUS.md).

## 1. Purpose

Validate a connected internal operating environment for ASAA, with governance and organization controls, people operations, procurement and finance foundations, shared identity/authorization, audit and PostgreSQL persistence. The POC is a working vertical slice, not a claim that the full enterprise operating model is complete.

## 2. Product boundary

ASAA is an internal platform designed around ASAA's own operating model. It is not a generic multi-company SaaS product and does not require every possible department, legal entity, policy or module to be activated. Project repositories remain independently owned and retain their own requirements, technology choices and release lifecycles.

## 3. Current executable scope

The repository currently contains:
- React 18/Vite web client in `src/` and static/PWA assets in `public/`.
- FastAPI service in `apps/ap-api`, using SQLAlchemy, Alembic and PostgreSQL/SQLite configuration.
- Governance: organization profile/hierarchy administration, master-data governance, authority delegations, decision register, access-review campaigns and role/permission assignment records.
- AP and procurement foundations: supplier records and purchase-request draft/submit/review.
- AR foundations: customers, invoices and receipts.
- People operations: employee directory/profile, employment lifecycle/history, onboarding/offboarding tasks, leave and employee asset records.
- Payroll foundations: restricted compensation, payroll periods/runs/entries, review and closure controls.
- Workforce finance: timesheet and expense claim foundations.
- Identity foundations: browser OIDC Authorization Code + PKCE flow and API RS256/JWKS verification with configurable MFA assurance claims.

These are foundational capabilities. A visible UI, API route or database model is not proof that the entire business workflow is accepted or production operational.

## 4. POC success criteria

1. A local user can start the web client and API using the documented setup.
2. API migrations can be applied to a disposable database.
3. API tests pass in the documented CI environment.
4. PostgreSQL 16 integration validates migrations and selected people/payroll persistence workflows.
5. Sensitive API routes fail closed when identity configuration is absent or invalid.
6. Explicit permissions and organization scoping are enforced by API dependencies and domain queries.
7. Sensitive workflows record application audit events and enforce their implemented review transitions.
8. The UI can call connected APIs for the currently integrated workflows.
9. Documentation distinguishes implemented foundations from unverified, preview-only and planned capabilities.
10. No production readiness claim is made without production infrastructure and owner acceptance evidence.

## 5. POC limitations and exclusions

- No production PostgreSQL instance, TLS deployment or restricted production database role has been validated.
- No identity provider/tenant has been selected and activated; automated account provisioning/deprovisioning is not integrated.
- Application audit records are not yet proven immutable or tamper-evident at the infrastructure layer.
- Backup, point-in-time recovery, restore, monitoring and disaster recovery are not operationally verified.
- Full procure-to-pay, accounting close, bank reconciliation and jurisdiction-specific tax/statutory behavior are not complete.
- Payroll is not a production payroll service until jurisdiction, policy, calculations, approvals, security and UAT are approved.
- Full UI/E2E, accessibility, compatibility, performance and security assurance are not complete.
- Commercial, CRM, project/product, service delivery, legal/compliance expansion, inventory, knowledge and advanced analytics remain planned or preview-only unless separately verified.

## 6. POC verification scenarios

| ID | Scenario | Current evidence |
|---|---|---|
| POC-01 | API quality and automated suite | CI VERIFIED — run 43411431405, commit ba87df7 |
| POC-02 | PostgreSQL 16 migrations and API integration | CI VERIFIED — run 43411431368, commit ba87df7 |
| POC-03 | Production database preflight | NEEDS TESTING — script exists; no production target |
| POC-04 | Real SSO/MFA provider flow | OWNER ACCEPTANCE PENDING — no provider activation |
| POC-05 | Identity lifecycle synchronization | NOT STARTED |
| POC-06 | UI and end-to-end workflows | NEEDS TESTING |
| POC-07 | Backup/restore and disaster recovery | NOT STARTED |
| POC-08 | Business workflow UAT | OWNER ACCEPTANCE PENDING |

## 7. POC exit decision

The POC demonstrates that foundational application slices and PostgreSQL CI integration exist. It does not authorize production launch. Exit to a first controlled release requires the P0 gates in [Project Status](PROJECT_STATUS.md) and [Release Readiness](RELEASE_READINESS.md) to be closed, with P1 workflows either accepted or disabled/excluded.
