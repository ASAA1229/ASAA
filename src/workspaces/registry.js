// Single registry of every portal workspace (category -> workspaces). src/workspaces/inventory.json documents the state of
// each one and tests/ui/workspace-inventory.test.js keeps the two in sync.
export const MODULE_GROUPS = [
  { group: "Workspace", items: [
    { name: "Overview", description: "Executive view across organization, delivery, people and finance.", capabilities: ["Company-wide KPIs and operating health", "Pending decisions, approvals and exceptions", "Portfolio, workforce and financial snapshots"], workflows: ["Review priorities", "Open a functional workspace", "Track unresolved items"], backend: "dashboard" }
  ]},
  { group: "Governance & Organization", items: [
    { name: "Organization & entities", description: "Manage organization profile, legal entities, business units and establishment lifecycle.", capabilities: ["Organization profile and legal-entity register", "Business units, divisions and departments", "Locations, effective dates and establishment gates"], workflows: ["Propose organization change", "Review and approve entity activation", "Maintain organization history"] },
    { name: "Departments & teams", description: "Configure the operating structure, teams, positions and reporting relationships.", capabilities: ["Department and team directory", "Positions, reporting lines and matrix membership", "Department ownership and capacity"], workflows: ["Create or update a team", "Assign team membership", "Review structure changes"] },
    { name: "Governance", description: "Maintain decisions, delegated authority, approval boundaries and policy exceptions.", capabilities: ["Decision register and rationale", "Time-bounded authority delegations", "Independent approval, rejection and revocation"], workflows: ["Propose a decision", "Request or review a delegation", "Record outcome and evidence"], backend: "governance" },
    { name: "Policies & procedures", description: "Control policy documents, versions, owners, approvals and acknowledgements.", capabilities: ["Policy and procedure catalogue", "Version, owner and effective-date history", "Acknowledgement and exception tracking"], workflows: ["Draft a policy", "Route for approval", "Publish and collect acknowledgement"] },
    { name: "Risk & internal controls", description: "Identify risks, control owners, incidents, findings and corrective actions.", capabilities: ["Risk register and assessments", "Control catalogue and testing", "Corrective action and exception tracking"], workflows: ["Register a risk", "Assess and assign controls", "Track remediation to closure"] }
  ]},
  { group: "Shared Platform", items: [
    { name: "Settings", description: "Configure workspace preferences, connection endpoints and device experience.", capabilities: ["Workspace and device preferences", "API connection settings", "Module configuration and accessibility"], workflows: ["Review workspace settings", "Configure a trusted connection", "Verify device experience"] },
    { name: "Identity & access", description: "Manage identity lifecycle, roles, permission scopes and privileged access governance.", capabilities: ["Users, external collaborators and access state", "Role templates and least-privilege permissions", "Organization, department, project and record scopes"], workflows: ["Request access", "Review and approve access", "Revoke or recertify access"] },
    { name: "Workflow & approvals", description: "Configure state transitions, maker-checker rules, approval matrices and escalations.", capabilities: ["Workflow definitions and versioning", "Submit, review, approve, reject and return", "Delegation, escalation and separation of duties"], workflows: ["Configure a workflow", "Assign approvers", "Monitor ageing and exceptions"] },
    { name: "Master data", description: "Govern reference domains, authoritative sources, stewardship and duplicate review.", capabilities: ["Domain owner and steward register", "Source provenance and record references", "Duplicate candidates and non-destructive supersession"], workflows: ["Register a domain", "Review duplicate candidates", "Supersede a source reference"], backend: "masterdata" },
    { name: "Documents & records", description: "Manage document metadata, classification, versions, retention and controlled access.", capabilities: ["Document register and metadata", "Classification, version and access history", "Retention, expiry and legal-hold references"], workflows: ["Register a document", "Review or acknowledge", "Apply retention disposition"] },
    { name: "Notifications & reminders", description: "Centralize notifications, delivery status, preferences and escalation reminders.", capabilities: ["In-app and external notification catalogue", "Delivery, retry and failure history", "Preferences, reminders and escalation rules"], workflows: ["Configure a notification", "Review delivery failures", "Escalate overdue work"] },
    { name: "Integrations & connectors", description: "Register API adapters and monitor credentials, synchronization and reconciliation.", capabilities: ["Provider and adapter registry", "Scoped credentials and revocation", "Sync health, retries, reconciliation and freshness"], workflows: ["Register a connector", "Authorize minimum scopes", "Run and reconcile a sync"] },
    { name: "Audit trail", description: "Review append-only evidence of actors, actions, outcomes and record changes.", capabilities: ["Actor, timestamp and action history", "Target, organization scope and correlation reference", "Evidence export subject to permissions"], workflows: ["Search audit events", "Inspect a record history", "Export an authorized evidence set"] }
  ]},
  { group: "People & Workforce", items: [
    { name: "People directory", description: "Manage employee and authorized collaborator profiles and organization placement.", capabilities: ["Employee and collaborator directory", "Employment and team relationships", "Restricted profile and document references"], workflows: ["Create a person record", "Update placement", "Review employment history"], backend: "hr" },
    { name: "Recruitment", description: "Manage vacancies, candidates, interviews, evaluations and offer approvals.", capabilities: ["Vacancy and hiring plan", "Candidate pipeline and interview schedule", "Evaluation and offer approval records"], workflows: ["Open a vacancy", "Evaluate a candidate", "Approve and issue an offer"] },
    { name: "Onboarding", description: "Coordinate versioned onboarding templates, assignments, tasks and evidence.", capabilities: ["Versioned onboarding templates", "Task ownership, due dates and assignments", "Documents, equipment and access-request checklist"], workflows: ["Create an onboarding plan", "Assign tasks", "Track completion"], backend: "onboarding" },
    { name: "Employment lifecycle", description: "Track employment changes with effective dates and preserved history.", capabilities: ["Join, transfer, promotion and contract changes", "Manager, team and position history", "Lifecycle status and effective dates"], workflows: ["Propose an employment change", "Review effective date", "Record lifecycle transition"], backend: "hr" },
    { name: "Attendance & shifts", description: "Manage attendance, rosters, shifts, holidays, overtime and work arrangements.", capabilities: ["Attendance and time events", "Shift, roster and holiday calendars", "Breaks, overtime and remote or field arrangements"], workflows: ["Publish a roster", "Record attendance exception", "Review overtime"] },
    { name: "Leave management", description: "Manage leave types, balances, accrual, calendars and independent approvals.", capabilities: ["Configurable leave types and eligibility", "Balances, accrual and holiday calendars", "Requests, reviews and decision history"], workflows: ["Request leave", "Review team coverage", "Approve or return a request"], backend: "hr" },
    { name: "Timesheets", description: "Capture period-based work entries, project allocation and independent review.", capabilities: ["Dated work entries and billable hours", "Project and task references", "Employee submission and independent reviewer decision"], workflows: ["Prepare a timesheet", "Submit a period", "Approve or reject with reason"], backend: "timesheets" },
    { name: "Compensation & payroll", description: "Control compensation records, payroll periods, runs, entries and approvals.", capabilities: ["Restricted compensation history", "Payroll period and run management", "Independent review, approval and closure"], workflows: ["Maintain compensation", "Prepare and submit a payroll run", "Review, approve and close"], backend: "payroll" },
    { name: "Performance & learning", description: "Coordinate goals, reviews, feedback, development plans and learning records.", capabilities: ["Goals and performance cycles", "Feedback and development plans", "Training, learning and certifications"], workflows: ["Set goals", "Run a review cycle", "Record learning completion"] },
    { name: "Employee relations", description: "Handle confidential grievances, investigations, appeals and restricted case evidence.", capabilities: ["Restricted case register", "Investigation and appeal milestones", "Confidential notes and access history"], workflows: ["Open a restricted case", "Assign an authorized investigator", "Record findings and closure"] },
    { name: "Offboarding", description: "Coordinate handover, asset return, final-settlement inputs and access revocation.", capabilities: ["Versioned exit checklists", "Handover and asset-return tracking", "Document retention and access-revocation evidence"], workflows: ["Open an exit case", "Complete handover and returns", "Verify closure"], backend: "hr" },
    { name: "Employee assets", description: "Track assigned equipment, custody, maintenance and returns.", capabilities: ["Asset issue and return history", "Ownership and condition records", "Maintenance and disposal references"], workflows: ["Issue an asset", "Record maintenance", "Accept return"], backend: "hr" }
  ]},
  { group: "Projects, Products & Technology", items: [
    { name: "Portfolio & projects", description: "Coordinate programs and projects with ownership, milestones, budgets and dependencies.", capabilities: ["Portfolio and project registry", "Scope, owners, milestones and budgets", "Dependencies, risks and evidence-based status"], workflows: ["Register a project", "Update milestone evidence", "Review portfolio health"] },
    { name: "Requirements & roadmaps", description: "Manage requirements, acceptance criteria, specifications, roadmaps and change history.", capabilities: ["Requirement and acceptance-criteria register", "Roadmaps, versions and dependencies", "Change requests and decision traceability"], workflows: ["Create a requirement", "Review acceptance criteria", "Approve a scope change"] },
    { name: "Products & lifecycle", description: "Manage product discovery, versions, features, pricing and retirement.", capabilities: ["Product and feature catalogue", "Version and lifecycle roadmap", "Pricing, packaging and retirement controls"], workflows: ["Create a product concept", "Plan a release", "Approve lifecycle transition"] },
    { name: "Repositories & engineering", description: "Track independent repositories, branches, code reviews and engineering tasks.", capabilities: ["Repository and branch metadata", "Engineering work and code-review references", "Project-specific stack and workflow preservation"], workflows: ["Discover repository evidence", "Review engineering work", "Record a verified change"] },
    { name: "QA & testing", description: "Coordinate test strategy, cases, runs, defects and release quality gates.", capabilities: ["Test plans and test cases", "Test runs and defect triage", "Quality gates and evidence links"], workflows: ["Plan a test cycle", "Record test results", "Review release readiness"] },
    { name: "CI/CD & pipelines", description: "Observe pipeline definitions, build status, approvals and deployment evidence.", capabilities: ["Provider-neutral pipeline registry", "Build and test run history", "Approval gates and execution evidence"], workflows: ["Connect a CI provider", "Inspect a pipeline run", "Review a failed quality gate"] },
    { name: "Environments & architecture", description: "Catalogue environments, architecture components, APIs, data stores and dependencies.", capabilities: ["Environment and configuration inventory", "Architecture and component catalogue", "API, event and data-store dependencies"], workflows: ["Register an environment", "Review a dependency", "Approve a configuration change"] },
    { name: "Releases & artifacts", description: "Track versioned releases, artifacts, deployment history and rollback readiness.", capabilities: ["Release plans and artifact provenance", "Environment promotion history", "Rollback and support readiness"], workflows: ["Prepare a release", "Approve promotion", "Verify deployment evidence"] },
    { name: "Technical knowledge", description: "Maintain engineering standards, technical decisions and reusable implementation knowledge.", capabilities: ["Architecture decisions and standards", "Reusable components and service catalogue", "Technical dependencies and ownership"], workflows: ["Propose a standard", "Review an architecture decision", "Publish reusable guidance"] }
  ]},
  { group: "Services & Operations", items: [
    { name: "Service catalogue", description: "Define internal and client-facing services, owners and service commitments.", capabilities: ["Service definitions and ownership", "Service tiers and operating hours", "Service dependencies and eligibility"], workflows: ["Create a service", "Approve service changes", "Review service health"] },
    { name: "Client delivery", description: "Coordinate client onboarding, statements of work, delivery schedules and milestones.", capabilities: ["Client onboarding and delivery plans", "SOW, milestones and deliverables", "Delivery ownership and acceptance"], workflows: ["Start a client engagement", "Schedule delivery", "Capture client acceptance"] },
    { name: "Work orders & scheduling", description: "Manage operational work orders, queues, assignments and schedules.", capabilities: ["Work order register and priorities", "Resource assignment and scheduling", "Checklists and completion evidence"], workflows: ["Create a work order", "Assign an owner", "Complete and verify work"] },
    { name: "Support & SLAs", description: "Track service requests, support queues, SLA commitments and escalations.", capabilities: ["Support cases and queues", "Response and resolution targets", "Escalation and customer communication"], workflows: ["Register a support request", "Triage and assign", "Resolve and review SLA"] },
    { name: "Procurement", description: "Manage purchase requests, quotations, purchase orders and receipt references.", capabilities: ["Purchase requisitions and approvals", "Supplier quotations and purchase orders", "Goods and service receipt references"], workflows: ["Raise a requisition", "Approve and issue an order", "Confirm receipt"] },
    { name: "Inventory & stock", description: "Track inventory, stock movement, custody, replenishment and disposal.", capabilities: ["Item catalogue and stock locations", "Receipts, issues and adjustments", "Reorder levels and stocktaking"], workflows: ["Receive stock", "Issue or transfer stock", "Reconcile inventory"] },
    { name: "Facilities, travel & logistics", description: "Coordinate facilities, travel requests, logistics and operational resources.", capabilities: ["Facilities and access requests", "Travel plans and approvals", "Logistics and resource allocation"], workflows: ["Submit a facilities request", "Approve travel", "Track logistics completion"] },
    { name: "Operational incidents", description: "Record operational incidents, impact, response actions and lessons learned.", capabilities: ["Incident register and severity", "Response timeline and ownership", "Corrective and preventive actions"], workflows: ["Declare an incident", "Coordinate response", "Review and close actions"] }
  ]},
  { group: "Sales & Customers", items: [
    { name: "CRM & customer accounts", description: "Manage customer accounts, contacts, relationships and account history.", capabilities: ["Customer and prospect accounts", "Contacts and relationship history", "Account ownership and segmentation"], workflows: ["Create an account", "Assign an account owner", "Review account health"] },
    { name: "Leads & sales pipeline", description: "Track leads, opportunities, qualification, pipeline stages and forecasts.", capabilities: ["Lead capture and qualification", "Opportunity stages and value", "Pipeline ownership and forecast"], workflows: ["Qualify a lead", "Advance an opportunity", "Review pipeline forecast"] },
    { name: "Proposals & quotations", description: "Prepare estimates, proposals, quotations and commercial approvals.", capabilities: ["Proposal and estimate versions", "Quotation line items and validity", "Pricing and discount approvals"], workflows: ["Prepare a proposal", "Review pricing", "Issue a quotation"] },
    { name: "Contracts & renewals", description: "Track commercial agreements, obligations, renewals and approval history.", capabilities: ["Contract register and versions", "Obligations and renewal dates", "Approval and evidence history"], workflows: ["Draft a contract", "Review obligations", "Track renewal"] },
    { name: "Orders & subscriptions", description: "Manage sales orders, subscriptions, service entitlements and renewals.", capabilities: ["Sales orders and fulfilment references", "Subscription terms and billing schedule", "Entitlements and renewal events"], workflows: ["Create an order", "Activate a subscription", "Process renewal"] },
    { name: "Customer onboarding & feedback", description: "Coordinate customer setup, communications, service access and satisfaction.", capabilities: ["Customer onboarding checklist", "Communication and service entitlements", "Feedback and satisfaction tracking"], workflows: ["Start onboarding", "Verify readiness", "Capture feedback"] },
    { name: "Marketing & campaigns", description: "Plan campaigns, channels, content, brand assets and partnerships.", capabilities: ["Campaign calendar and objectives", "Content and channel plans", "Brand assets and partner records"], workflows: ["Plan a campaign", "Approve content", "Review campaign outcomes"] }
  ]},
  { group: "Finance & Accounting", items: [
    { name: "AR · Receivables", description: "Manage customers, invoices, receipts, allocations and outstanding balances.", capabilities: ["Customer master and invoice lifecycle", "Receipt capture and allocation", "Outstanding balances and collection references"], workflows: ["Create and issue an invoice", "Record a receipt", "Allocate receipt to invoices"], backend: "ar" },
    { name: "AP · Payables", description: "Manage suppliers and the purchasing-to-payment lifecycle.", capabilities: ["Supplier directory and verification", "Supplier invoice capture and matching", "Payment batches and reconciliation"], workflows: ["Verify a supplier", "Match a supplier invoice", "Prepare a payment batch"], backend: "ap" },
    { name: "Budgets & forecasting", description: "Manage organizational, departmental and project budgets and forecast approvals.", capabilities: ["Budget and cost-centre register", "Forecast assumptions and versions", "Variance and approval tracking"], workflows: ["Prepare a budget", "Submit a forecast", "Review budget variance"] },
    { name: "Expenses", description: "Manage employee claims, independent review and separate reimbursement recording.", capabilities: ["Expense claims and receipt references", "Policy and duplicate checks", "Approval and reimbursement evidence"], workflows: ["Submit an expense claim", "Review and approve", "Record reimbursement"], backend: "expenses" },
    { name: "Cash flow & treasury", description: "Monitor cash positions, forecasts, bank accounts and payment obligations.", capabilities: ["Cash position and cash-flow forecast", "Bank account references", "Payment obligations and liquidity scenarios"], workflows: ["Import a statement", "Reconcile cash movements", "Review cash forecast"] },
    { name: "Accounting & reconciliation", description: "Manage chart of accounts, journals, dimensions and reconciliation evidence.", capabilities: ["Chart of accounts and accounting dimensions", "Journal and posting references", "Bank and subledger reconciliation"], workflows: ["Prepare a journal", "Review reconciliation", "Close an accounting period"] },
    { name: "Financial reporting", description: "Provide controlled financial statements, aging, profitability and management reporting.", capabilities: ["Receivables and payables aging", "Revenue, cost and margin reporting", "Source lineage and report access controls"], workflows: ["Build a financial report", "Review source lineage", "Export an authorized report"] },
    { name: "Payroll accounting", description: "Connect approved payroll outputs to finance journals and reconciliation.", capabilities: ["Approved payroll export references", "Payroll journal mapping", "Reconciliation and period close"], workflows: ["Prepare a payroll export", "Review journal mapping", "Reconcile payroll posting"] }
  ]},
  { group: "Legal, Security & Compliance", items: [
    { name: "Legal contracts", description: "Maintain legal agreements, obligations, renewals and legal review evidence.", capabilities: ["Legal contract repository", "Obligation and renewal register", "Review and approval history"], workflows: ["Register an agreement", "Assign legal review", "Track obligations"] },
    { name: "Compliance & obligations", description: "Track confirmed obligations, compliance calendars, evidence and corrective actions.", capabilities: ["Obligation and policy register", "Compliance calendar and evidence", "Findings and remediation"], workflows: ["Register an applicable obligation", "Collect evidence", "Review compliance status"] },
    { name: "Privacy & data retention", description: "Manage privacy requests, consent, retention, legal holds and controlled deletion.", capabilities: ["Consent and privacy request register", "Retention schedules and legal holds", "Export and lawful deletion evidence"], workflows: ["Receive a privacy request", "Review retention constraints", "Record authorized disposition"] },
    { name: "Security operations", description: "Coordinate security incidents, vulnerability remediation and security assessments.", capabilities: ["Security incident register", "Risk and vulnerability findings", "Remediation and breach-response evidence"], workflows: ["Triage a security incident", "Assign remediation", "Verify closure"] },
    { name: "Access reviews", description: "Review privileged access, periodic certification and identity lifecycle evidence.", capabilities: ["Access review campaigns", "Privileged account inventory", "Certification and revocation history"], workflows: ["Launch an access review", "Certify or revoke access", "Close review evidence"] },
    { name: "Backup & recovery", description: "Track backup coverage, restore tests, recovery objectives and readiness.", capabilities: ["Backup policy and job evidence", "Restore-test records", "Recovery objectives and incident runbooks"], workflows: ["Review backup health", "Run an authorized restore test", "Record recovery readiness"] }
  ]},
  { group: "Knowledge & Collaboration", items: [
    { name: "Knowledge base", description: "Publish searchable knowledge, controlled documents and version history.", capabilities: ["Knowledge articles and collections", "Versioning and ownership", "Search and access controls"], workflows: ["Draft an article", "Review and publish", "Retire outdated guidance"] },
    { name: "Announcements & communication", description: "Manage internal announcements, communication channels and delivery history.", capabilities: ["Announcements and audience targeting", "Team communication spaces", "Delivery and acknowledgement"], workflows: ["Draft an announcement", "Approve and publish", "Review acknowledgements"] },
    { name: "Team spaces & collaboration", description: "Provide team workspaces, discussions, shared actions and collaboration context.", capabilities: ["Team spaces and membership", "Discussions and shared files", "Action ownership and follow-up"], workflows: ["Create a team space", "Start a discussion", "Track agreed actions"] },
    { name: "Calendar & meetings", description: "Coordinate calendars, meetings, minutes, decisions and follow-up actions.", capabilities: ["Shared calendars and events", "Meeting agendas and minutes", "Decisions and action items"], workflows: ["Schedule a meeting", "Record minutes", "Assign follow-up actions"] },
    { name: "Forms & service requests", description: "Provide configurable forms, requests, approvals and controlled external sharing.", capabilities: ["Form catalogue and field sensitivity", "Request queues and approvals", "External sharing controls"], workflows: ["Publish a form", "Submit a request", "Review and fulfil request"] }
  ]},
  { group: "Analytics & Intelligence", items: [
    { name: "Reports & dashboards", description: "Present role-scoped KPIs and operational, workforce, delivery and finance reporting.", capabilities: ["Executive and department dashboards", "Configurable KPIs and targets", "Permission-aware reports and exports"], workflows: ["Configure a dashboard", "Review KPI variance", "Export a permitted report"], backend: "reports" },
    { name: "Forecasting & scenarios", description: "Model forecasts and scenarios with visible assumptions and uncertainty.", capabilities: ["Forecast versions and assumptions", "Scenario comparisons", "Confidence and uncertainty disclosure"], workflows: ["Create a scenario", "Adjust assumptions", "Compare forecast outcomes"] },
    { name: "AI intelligence", description: "Provide evidence-grounded search, summarization and recommendations with human oversight.", capabilities: ["Approved-source search and summaries", "Recommendations with provenance", "Confidence, citations and feedback"], workflows: ["Ask an evidence-grounded question", "Review supporting sources", "Accept or dismiss a recommendation"] },
    { name: "Automation & agents", description: "Govern scoped triggers and actions with dry-run, approval, audit and recovery.", capabilities: ["Automation catalogue and triggers", "Permission-scoped actions and dry-run", "Logs, stop controls and compensation"], workflows: ["Design an automation", "Test in dry-run", "Approve and monitor execution"] }
  ]}
];

// Workspaces rendered by a real, API-wired component (not the generic preview). Keep in sync with inventory.json.
export const WIRED_WORKSPACES = [
  "Contracts & renewals",
  "Backup & recovery",
  "Accounting & reconciliation",
  "Documents & records",
  "Financial reporting",
  "Governance",
  "Notifications & reminders",
  "Audit trail",
  "Policies & procedures",
  "Risk & internal controls",
  "Compliance & obligations",
  "Legal contracts",
  "Privacy & data retention",
  "Knowledge base",
  "Announcements & communication",
  "Integrations & connectors",
  "Workflow & approvals",
  "Security operations",
  "Operational incidents",
  "Overview",
  "AR · Receivables",
  "AP · Payables",
  "Procurement",
  "Timesheets",
  "Expenses",
  "People directory",
  "Employment lifecycle",
  "Onboarding",
  "Offboarding",
  "Leave management",
  "Employee assets",
  "Compensation & payroll",
  "Organization & entities",
  "Departments & teams",
  "Master data",
  "Identity & access",
  "Access reviews",
  "Settings",
  "Reports & dashboards",
];

// Workspaces backed by governed registers (GET /api/v1/registers/<type>); value = register types shown as tabs.
export const REGISTER_WORKSPACES = {
  "Policies & procedures": [
    "policy"
  ],
  "Risk & internal controls": [
    "risk",
    "control"
  ],
  "Compliance & obligations": [
    "obligation"
  ],
  "Legal contracts": [
    "contract"
  ],
  "Privacy & data retention": [
    "retention_rule"
  ],
  "Knowledge base": [
    "article"
  ],
  "Announcements & communication": [
    "announcement"
  ],
  "Integrations & connectors": [
    "integration"
  ],
  "Workflow & approvals": [
    "workflow_definition"
  ],
  "Security operations": [
    "security_incident"
  ],
  "Operational incidents": [
    "operational_incident"
  ],
  "Documents & records": [
    "document"
  ],
  "Portfolio & projects": [
    "project"
  ],
  "Requirements & roadmaps": [
    "requirement"
  ],
  "Products & lifecycle": [
    "product"
  ],
  "Repositories & engineering": [
    "repository"
  ],
  "QA & testing": [
    "test_plan"
  ],
  "CI/CD & pipelines": [
    "pipeline"
  ],
  "Environments & architecture": [
    "environment"
  ],
  "Releases & artifacts": [
    "release"
  ],
  "Technical knowledge": [
    "technical_article"
  ],
  "Service catalogue": [
    "service"
  ],
  "Client delivery": [
    "engagement"
  ],
  "Work orders & scheduling": [
    "work_order"
  ],
  "Support & SLAs": [
    "sla"
  ],
  "Inventory & stock": [
    "inventory_item"
  ],
  "Facilities, travel & logistics": [
    "facility_request"
  ],
  "CRM & customer accounts": [
    "account"
  ],
  "Leads & sales pipeline": [
    "lead"
  ],
  "Proposals & quotations": [
    "proposal"
  ],
  "Orders & subscriptions": [
    "order"
  ],
  "Customer onboarding & feedback": [
    "feedback"
  ],
  "Marketing & campaigns": [
    "campaign"
  ],
  "Team spaces & collaboration": [
    "team_space"
  ],
  "Calendar & meetings": [
    "meeting"
  ],
  "Forms & service requests": [
    "form_request"
  ],
  "Recruitment": [
    "vacancy"
  ],
  "Performance & learning": [
    "goal"
  ],
  "Budgets & forecasting": [
    "budget"
  ],
  "Forecasting & scenarios": [
    "scenario"
  ],
  "Automation & agents": [
    "automation"
  ],
  "Attendance & shifts": [
    "shift_roster"
  ],
  "Employee relations": [
    "er_case"
  ],
  "AI intelligence": [
    "ai_use_case"
  ],
  "Contracts & renewals": [
    "contract"
  ]
};

// Every workspace that renders a real component instead of the generic preview (functional or partial).
// Partially implemented workspaces that use a report view instead of a register.
export const REPORT_PARTIAL_WORKSPACES = ["Cash flow & treasury", "Payroll accounting"];
export const ROUTED_WORKSPACES = [...new Set([...WIRED_WORKSPACES, ...REPORT_PARTIAL_WORKSPACES, ...Object.keys(REGISTER_WORKSPACES)])];
