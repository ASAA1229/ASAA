# ASAA Project Scope

**Project:** ASAA — internal enterprise operating and organization-management platform  
**Repository:** https://github.com/ASAA1229/ASAA  
**Scope version:** 2026-11-14 | **Status:** planning scope; implementation evidence tracked separately

## Mission
Provide ASAA with governed capabilities for organization administration, workforce, finance, commercial operations, delivery management, reporting, security and internal operations.

## Users
Organization owner and management; HR; finance; operations; employees; authorized vendors/customers where a workflow explicitly permits external access.

## In scope
- Organization structure, governance, authority and administration.
- Identity, authentication, authorization, roles, sessions and lifecycle.
- People, HR, employment, onboarding/offboarding, leave, payroll, timesheets and expenses.
- Suppliers, procurement, accounts payable and accounts receivable.
- Customer/vendor and commercial management.
- Project, product, resource and service-delivery management.
- Reporting, analytics, knowledge, documents and communications.
- Security, privacy, audit, integrations, DevOps, observability, backup and continuity.

## Conditional / not yet approved
Production rollout, external identity-provider activation, production hosting, paid vendors, unapproved finance/business policies, and future domains without approved requirements.

## Architecture and constraints
No single stack is mandated across ASAA. Current repository documentation describes React/Vite frontend, FastAPI/SQLAlchemy API and PostgreSQL migration support. Preserve module boundaries and verified work. Apply least privilege, privacy, auditability and explicit business ownership. Do not equate code foundations or preview screens with accepted operational workflows.

## Current status summary
Repository documentation records substantial local API/UI/security/database and browser-test work and a repository maturity judgement of 5.6/10. Production release is recorded as **NO-GO**. External identity/provider activation, production infrastructure, business UAT, independent assurance, production recovery and operational readiness remain open. See `docs/PROJECT_STATUS.md` for detailed evidence and gates.


---

# ASAA Project Scope — 2026-11-14

Purpose: internal enterprise operating and management platform for ASAA.

Users: organization owner/management, HR, finance, operations, employees and explicitly authorized external parties.

In scope: governance and organization administration; identity and authorization; workforce/HR lifecycle; onboarding/offboarding; leave, payroll, timesheets and expenses; suppliers, procurement and AP; AR and customer/commercial workflows; project/resource management; reporting/analytics; audit, security, integrations, DevOps and operations.

Conditional: production rollout, provider activation, paid services and business policies without named approval. Future domains remain planned until individually specified and evidenced.

Architecture: no forced ecosystem-wide stack. Current repo docs describe React/Vite web, FastAPI/SQLAlchemy API and PostgreSQL migrations. Preserve module-level choices and verified work. Apply least privilege, auditability, privacy and explicit ownership.

Current evidence: repo status reports local API/UI/E2E/security/database verification and 5.6/10 repository maturity; production remains NO-GO. Real identity provider, production DB/hosting, business UAT, recovery objectives, live monitoring and operational gates remain open.
