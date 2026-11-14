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
