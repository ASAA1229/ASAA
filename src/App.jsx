import ProcurementWorkspace from "./ProcurementWorkspace.jsx";
import SupplierWorkspace from "./SupplierWorkspace.jsx";
import ReceivablesWorkspace from "./ReceivablesWorkspace.jsx";
import WorkforceFinanceWorkspace from "./WorkforceFinanceWorkspace.jsx";
import AdministrationWorkspace from "./AdministrationWorkspace.jsx";
import { completeSsoSignIn, isSsoConfigured, startSsoSignIn } from "./identity/oidc.js";

import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownLeft, ArrowUpRight, Bell, BriefcaseBusiness, Building2, CalendarDays,
  Check, ChevronDown, CircleHelp, Clock3, Command, CreditCard, FileCheck2, FileText,
  Gauge, LayoutDashboard, Menu, Plus, Search, Settings2, ShieldCheck, Users, Wallet,
  X, RefreshCw, LogOut, Smartphone, Monitor, Laptop, Receipt, ChartNoAxesCombined,
  Landmark, ClipboardList, CircleDollarSign, UserRound
} from "lucide-react";

const API_DEFAULT = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const MODULE_GROUPS = [
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
const MODULE_ICONS = {
  "Overview": LayoutDashboard, "Organization & entities": Building2, "Departments & teams": Users,
  "Governance": ShieldCheck, "Policies & procedures": FileCheck2, "Risk & internal controls": ShieldCheck,
  "Identity & access": UserRound, "Workflow & approvals": ClipboardList, "Master data": Landmark,
  "Documents & records": FileText, "Notifications & reminders": Bell, "Integrations & connectors": Activity,
  "Audit trail": FileCheck2, "People directory": Users, "Recruitment": BriefcaseBusiness,
  "Onboarding": UserRound, "Employment lifecycle": Users, "Attendance & shifts": CalendarDays,
  "Leave management": CalendarDays, "Timesheets": Clock3, "Compensation & payroll": Wallet,
  "Performance & learning": Gauge, "Employee relations": ShieldCheck, "Offboarding": LogOut,
  "Employee assets": Laptop, "Portfolio & projects": BriefcaseBusiness, "Requirements & roadmaps": ClipboardList,
  "Products & lifecycle": Building2, "Repositories & engineering": Command, "QA & testing": Check,
  "CI/CD & pipelines": Activity, "Environments & architecture": Monitor, "Releases & artifacts": FileCheck2,
  "Technical knowledge": FileText, "Service catalogue": BriefcaseBusiness, "Client delivery": Users,
  "Work orders & scheduling": CalendarDays, "Support & SLAs": CircleHelp, "Procurement": CreditCard,
  "Inventory & stock": Building2, "Facilities, travel & logistics": Landmark, "Operational incidents": Activity,
  "CRM & customer accounts": Users, "Leads & sales pipeline": ChartNoAxesCombined,
  "Proposals & quotations": FileText, "Contracts & renewals": FileCheck2, "Orders & subscriptions": CreditCard,
  "Customer onboarding & feedback": UserRound, "Marketing & campaigns": Gauge,
  "AR · Receivables": ArrowDownLeft, "AP · Payables": ArrowUpRight, "Budgets & forecasting": ChartNoAxesCombined,
  "Expenses": Receipt, "Cash flow & treasury": Wallet, "Accounting & reconciliation": Landmark,
  "Financial reporting": ChartNoAxesCombined, "Payroll accounting": CircleDollarSign,
  "Legal contracts": FileText, "Compliance & obligations": ShieldCheck, "Privacy & data retention": ShieldCheck,
  "Security operations": ShieldCheck, "Access reviews": UserRound, "Backup & recovery": RefreshCw,
  "Knowledge base": FileText, "Announcements & communication": Bell, "Team spaces & collaboration": Users,
  "Calendar & meetings": CalendarDays, "Forms & service requests": ClipboardList,
  "Reports & dashboards": ChartNoAxesCombined, "Forecasting & scenarios": ChartNoAxesCombined,
  "AI intelligence": Gauge, "Automation & agents": Activity, "Settings": Settings2
};
const NAV = MODULE_GROUPS.map(group => ({ group: group.group, items: group.items.map(item => [item.name, MODULE_ICONS[item.name] || LayoutDashboard]) }));
const MODULE_INFO = Object.fromEntries(MODULE_GROUPS.flatMap(group => group.items.map(item => [item.name, { ...item, group: group.group }])));

const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value || 0));
const dateLabel = value => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const decodeClaims = token => {
  try { return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); } catch { return {}; }
};

function App() {
  const [section, setSection] = useState("Overview");
  const [mobileNav, setMobileNav] = useState(false);
  const [navSearch, setNavSearch] = useState("");
  const [previewMode, setPreviewMode] = useState(false);
  const [apiBase, setApiBase] = useState(API_DEFAULT);
  const [tokenInput, setTokenInput] = useState("");
  const [token, setToken] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState({ suppliers: [], customers: [], invoices: [], receipts: [], timesheets: [], expenses: [], purchaseRequests: [] });
  const [modal, setModal] = useState("");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState("");
  const [ssoError, setSsoError] = useState("");
  const claims = useMemo(() => decodeClaims(token), [token]);

  const api = async (path, options = {}) => {
    const response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(options.headers || {}) }
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      if (response.status === 401) {
        setToken(""); setTokenInput(""); setConnected(false);
        setData({ suppliers: [], customers: [], invoices: [], receipts: [], timesheets: [], expenses: [], purchaseRequests: [] });
      }
      throw new Error(typeof body.detail === "string" ? body.detail : body.detail ? JSON.stringify(body.detail) : `Request failed (${response.status})`);
    }
    return response.status === 204 ? null : response.json();
  };

  const refresh = async () => {
    if (!token) return;
    setLoading(true); setError("");
    const jobs = [
      ["suppliers", "/api/v1/ap/suppliers"], ["customers", "/api/v1/ar/customers"],
      ["invoices", "/api/v1/ar/invoices"], ["receipts", "/api/v1/ar/receipts"],
      ["timesheets", "/api/v1/workforce-finance/timesheets"], ["expenses", "/api/v1/workforce-finance/expenses"], ["purchaseRequests", "/api/v1/ap/purchase-requests"]
    ];
    const results = await Promise.all(jobs.map(async ([key, path]) => {
      try { return [key, await api(path)]; }
      catch (e) { return [key, [], e.message]; }
    }));
    const next = Object.fromEntries(results.map(([key, value]) => [key, Array.isArray(value) ? value : []]));
    const failures = results.filter(([, , message]) => message).map(([key, , message]) => `${key}: ${message}`);
    setData(next); setConnected(true);
    if (failures.length === jobs.length) setError("The API could not be reached or this account has no read permissions. Check the API URL and access permissions.");
    else if (failures.length) setError(`Some areas are unavailable for this account: ${failures.join(" · ")}`);
    setLoading(false);
  };

  const connect = async () => {
    if (!tokenInput.trim()) { setError("Enter an access token issued by the configured identity provider."); return; }
    setToken(tokenInput.trim()); setError(""); setLoading(true);
  };
  useEffect(() => { if (token) refresh(); }, [token]);
  useEffect(() => { completeSsoSignIn().then(accessToken => { if (accessToken) { setToken(accessToken); setTokenInput(""); setSsoError(""); } }).catch(err => setSsoError(err.message || "SSO sign-in failed.")); }, []);
  const signInSso = async () => { try { setSsoError(""); await startSsoSignIn(); } catch (err) { setSsoError(err.message || "SSO sign-in could not start."); } };
  useEffect(() => { if (!toast) return; const id = setTimeout(() => setToast(""), 2800); return () => clearTimeout(id); }, [toast]);

  const stats = useMemo(() => {
    const outstanding = data.invoices.reduce((sum, row) => sum + Number(row.outstanding || 0), 0);
    const payables = data.suppliers.filter(x => x.status === "Pending Verification").length;
    const submittedTime = data.timesheets.filter(x => x.status === "Submitted").length;
    const pendingExpenses = data.expenses.filter(x => ["Submitted", "Approved"].includes(x.status)).length;
    return { outstanding, payables, submittedTime, pendingExpenses };
  }, [data]);

  const createRecord = async (kind, payload) => {
    const routes = { expense: "/api/v1/workforce-finance/expenses", customer: "/api/v1/ar/customers", supplier: "/api/v1/ap/suppliers" };
    await api(routes[kind], { method: "POST", body: JSON.stringify(payload) });
    setModal(""); setToast("Record created successfully."); await refresh();
  };

  const visibleItems = NAV.flatMap(group => group.items).filter(([name]) => name === section);
  const activeIcon = visibleItems[0]?.[1] || LayoutDashboard;
  const ActiveIcon = activeIcon;

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-mark">A</div><div><strong>ASAA</strong><span>OPERATING PLATFORM</span></div><button className="icon-btn sidebar-close" onClick={() => setMobileNav(false)}><X size={18}/></button></div>
      <div className="workspace-switch"><div className="workspace-avatar">A</div><div><b>ASAA Workspace</b><small>Founder workspace</small></div><ChevronDown size={15}/></div>
      <div className="sidebar-search"><Search size={15}/><input value={navSearch} onChange={e=>setNavSearch(e.target.value)} placeholder="Find a module…"/>{navSearch && <button onClick={()=>setNavSearch("")} aria-label="Clear module search"><X size={13}/></button>}</div>
      <nav>
        {NAV.map(group => <div className="nav-group" key={group.group}><small className="nav-caption">{group.group}</small>{group.items.filter(([name])=>name.toLowerCase().includes(navSearch.toLowerCase())).map(([name, Icon]) => <button key={name} className={`nav-item ${section === name ? "active" : ""}`} onClick={() => { setSection(name); setMobileNav(false); setSearch(""); }}><Icon size={17}/><span>{name}</span>{name === "Expenses" && stats.pendingExpenses > 0 && token && <i>{stats.pendingExpenses}</i>}</button>)}</div>)}
      </nav>
      <div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={16}/><span>Secure workspace<br/><small>Access controlled by permissions</small></span></div><button className="nav-item" onClick={() => setModal("connection")}><Settings2 size={17}/>Connection settings</button></div>
      <div className="sidebar-user"><div className="user-avatar">AD</div><div><b>{claims.name || (token ? "ASAA Administrator" : "Preview visitor")}</b><small>{token ? "Founder · CEO · Director · Current responsibilities" : "Unauthenticated UI preview"}</small></div><button className="icon-btn" title="Sign out" onClick={() => { setToken(""); setTokenInput(""); setConnected(false); setData({ suppliers: [], customers: [], invoices: [], receipts: [], timesheets: [], expenses: [], purchaseRequests: [] }); }}><LogOut size={16}/></button></div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <button className="icon-btn mobile-menu" onClick={() => setMobileNav(true)}><Menu size={20}/></button>
        <div className="crumb"><span>ASAA</span><b>/</b><strong>{section}</strong></div>
        <div className="top-actions"><div className="system-status"><span className={connected ? "status-dot online" : "status-dot"}/>{connected ? "API connected" : "Not connected"}</div><button className="icon-btn" title="Help"><CircleHelp size={18}/></button><button className="icon-btn notification-btn" title="Notifications"><Bell size={18}/><i/></button><div className="top-avatar">{token ? "AD" : "PV"}</div></div>
      </header>

      <div className="content">
        {!token && !previewMode ? <ConnectScreen apiBase={apiBase} setApiBase={setApiBase} tokenInput={tokenInput} setTokenInput={setTokenInput} connect={connect} error={error} ssoError={ssoError} ssoConfigured={isSsoConfigured} onSsoSignIn={signInSso} onExplore={() => setPreviewMode(true)}/> :
        <>
          {!token && <div className="preview-banner"><ShieldCheck size={16}/><span><b>UI preview mode</b> — live company records are hidden until you connect an authorized API session.</span><button className="btn btn-quiet" onClick={() => setModal("connection")}>Connect live data</button></div>}
          <div className="welcome-row"><div><div className="eyebrow">{new Date().toLocaleDateString("en-IN", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).toUpperCase()} · EXECUTIVE OVERVIEW</div><h1>{section === "Overview" ? "Good afternoon." : section}</h1><p>{section === "Overview" ? "Your company, operations and financial position at a glance." : sectionDescription(section)}</p></div><div className="welcome-actions">{token && <><button className="btn btn-quiet" onClick={refresh} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""}/> Refresh</button><button className="btn btn-primary" onClick={() => setModal("quick")}><Plus size={16}/> Create new</button></>}</div></div>
          {error && <div className="notice"><Activity size={16}/><span>{error}</span></div>}
          {section === "Overview" && (token ? <Overview data={data} stats={stats} loading={loading} setSection={setSection} setModal={setModal}/> : <PreviewOverview setSection={setSection}/>)}
          {section === "AR · Receivables" && (token ? <ReceivablesWorkspace customers={data.customers} invoices={data.invoices} receipts={data.receipts} api={api} claims={claims} onChanged={refresh} onAddCustomer={() => setModal("customer")}/> : <ModuleWorkspace name={section} connected={false} setSection={setSection}/>)}
          {section === "AP · Payables" && (token ? <><SupplierWorkspace suppliers={data.suppliers} api={api} claims={claims} onChanged={refresh}/><ProcurementWorkspace requests={data.purchaseRequests} suppliers={data.suppliers} api={api} claims={claims} onChanged={refresh}/></> : <ModuleWorkspace name={section} connected={false} setSection={setSection}/>)}
          {section === "Procurement" && (token ? <ProcurementWorkspace requests={data.purchaseRequests} api={api} claims={claims} onChanged={refresh}/> : <ModuleWorkspace name={section} connected={false} setSection={setSection}/>)}
          {section === "Timesheets" && (token ? <WorkforceFinanceWorkspace kind="timesheet" records={data.timesheets} api={api} claims={claims} onChanged={refresh}/> : <ModuleWorkspace name={section} connected={false} setSection={setSection}/>)}
          {section === "Expenses" && (token ? <WorkforceFinanceWorkspace kind="expense" records={data.expenses} api={api} claims={claims} onChanged={refresh}/> : <ModuleWorkspace name="Expenses" connected={false} setSection={setSection}/>)}
          {section === "Governance" && <ModuleWorkspace name={section} connected={!!token} setSection={setSection} claims={claims}/>}
          {["Organization & entities","Departments & teams","Master data","Identity & access","Access reviews"].includes(section) && <AdministrationWorkspace name={section} api={api} claims={claims} connected={!!token} onChanged={refresh}/>}
          {section === "Reports" && (token ? <Reports data={data} stats={stats}/> : <ModuleWorkspace name="Reports & dashboards" connected={false} setSection={setSection}/>)}
          {section === "Settings" && <SettingsPanel apiBase={apiBase} setApiBase={setApiBase} claims={claims} openConnection={() => setModal("connection")}/>}
          {!["Overview","AR · Receivables","AP · Payables","Procurement","Timesheets","Expenses","Governance","Reports","Settings","Organization & entities","Departments & teams","Master data","Identity & access","Access reviews"].includes(section) && <ModuleWorkspace name={section} connected={!!token} setSection={setSection} claims={claims}/>}
          <footer className="page-footer"><span>ASAA · Enterprise Operating Platform</span><span>Secure by design <ShieldCheck size={13}/></span></footer>
        </>}
      </div>
    </main>

    {modal && <Modal title={modal === "connection" ? "API connection" : modal === "expense" ? "New expense claim" : modal === "customer" ? "Add customer" : modal === "supplier" ? "Add supplier" : "Create a record"} onClose={() => setModal("")}>
      {modal === "connection" ? <ConnectionForm apiBase={apiBase} setApiBase={setApiBase} tokenInput={tokenInput} setTokenInput={setTokenInput} connect={connect} connected={connected} ssoConfigured={isSsoConfigured} onSsoSignIn={signInSso} ssoError={ssoError}/> :
       modal === "quick" ? <div className="quick-grid">{[["expense","Expense claim",Receipt],["customer","Customer",Users],["supplier","Supplier",Building2]].map(([key,label,Icon]) => <button className="quick-option" key={key} onClick={() => setModal(key)}><Icon size={20}/><b>{label}</b><span>Create a new {label.toLowerCase()}</span></button>)}</div> :
       <RecordForm kind={modal} onCancel={() => setModal("")} onSave={createRecord}/>}
    </Modal>}
    {toast && <div className="toast"><Check size={16}/>{toast}</div>}
  </div>;
}

function ConnectScreen({ apiBase, setApiBase, tokenInput, setTokenInput, connect, error, ssoError, ssoConfigured, onSsoSignIn, onExplore }) {
  return <div className="connect-layout"><div className="connect-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="connect-emblem">A</div><div className="art-label"><span/> ONE WORKSPACE. EVERYWHERE.</div></div><div className="connect-card"><div className="eyebrow">ASAA · EXECUTIVE ACCESS</div><h1>Welcome back.</h1><p>Connect to your secure ASAA workspace to manage finance, people and operations from any device.</p><label>API endpoint</label><input value={apiBase} onChange={e => setApiBase(e.target.value)} placeholder="https://api.your-domain.com"/>{ssoConfigured && <button className="btn btn-primary btn-full" onClick={onSsoSignIn}>Sign in with SSO <ArrowUpRight size={16}/></button>}{ssoError && <div className="form-error">{ssoError}</div>}<div className="connect-divider">Development access</div><label>Identity access token</label><textarea rows="3" value={tokenInput} onChange={e => setTokenInput(e.target.value)} placeholder="Paste a development access token"/><small className="field-help">Development fallback only. The token stays in memory and is not saved to this device.</small>{error && <div className="form-error">{error}</div>}<button className="btn btn-quiet btn-full" onClick={connect}>Connect with development token <ArrowUpRight size={16}/></button><button className="btn btn-quiet btn-full" onClick={onExplore}>Explore all module UIs <LayoutDashboard size={15}/></button><div className="connect-security"><ShieldCheck size={16}/> Verified by your configured identity provider</div><div className="connect-foot">Desktop · Tablet · Mobile · Installable app</div></div></div>;
}

function Overview({ data, stats, loading, setSection, setModal }) {
  const pending = [...data.timesheets.filter(x => x.status === "Submitted").map(x => ({ title: "Timesheet awaiting review", sub: `${x.employee_reference || x.employee_subject} · ${x.total_hours} hours`, date: x.period_start, type: "TMS" })), ...data.expenses.filter(x => x.status === "Submitted").map(x => ({ title: x.description, sub: `${money(x.amount, x.currency)} · Expense claim`, date: x.expense_date, type: "Expense" }))].slice(0, 5);
  return <><div className="metric-grid">
    <Metric label="Receivables outstanding" value={money(stats.outstanding)} note="From current AR invoices" icon={ArrowDownLeft} tone="gold"/>
    <Metric label="Customers" value={data.customers.length} note="Registered customer records" icon={Users}/>
    <Metric label="Suppliers" value={data.suppliers.length} note="Supplier directory" icon={Building2}/>
    <Metric label="Awaiting review" value={stats.submittedTime + data.expenses.filter(x => x.status === "Submitted").length} note="Timesheets and expenses" icon={FileCheck2} tone="blue"/>
  </div><div className="dashboard-grid"><section className="panel cash-panel"><div className="panel-heading"><div><h2>Financial snapshot</h2><p>Live figures from connected finance records</p></div><button className="text-link" onClick={() => setSection("AR · Receivables")}>View receivables <ArrowUpRight size={14}/></button></div><div className="cash-total">{money(stats.outstanding)}<span>Outstanding receivables</span></div><div className="mini-bars">{[38,55,44,70,58,84,65,92,73,100,78,88].map((h,i)=><div key={i} style={{height:`${h}%`}}/>)}</div><div className="chart-legend"><span><i/> Receivables trend visual (illustrative)</span><small>Not a time-series report</small></div></section><section className="panel action-panel"><div className="panel-heading"><div><h2>Quick actions</h2><p>Common tasks across your workspace</p></div><Command size={17}/></div><div className="action-grid">{[["Add customer",Users,"customer"],["Add supplier",Building2,"supplier"],["Submit expense",Receipt,"expense"],["View timesheets",Clock3,"Timesheets"]].map(([label,Icon,action])=><button key={label} onClick={() => action === "Timesheets" ? setSection(action) : setModal(action)}><span><Icon size={18}/></span><b>{label}</b><ArrowUpRight size={14}/></button>)}</div></section><section className="panel approvals-panel"><div className="panel-heading"><div><h2>Needs your attention</h2><p>Items currently submitted for review</p></div><span className="count-pill">{pending.length}</span></div>{pending.length ? <div className="attention-list">{pending.map((item,i)=><div className="attention-item" key={i}><div className="attention-icon"><FileText size={17}/></div><div className="attention-copy"><b>{item.title}</b><small>{item.sub}</small></div><div className="attention-meta"><span>{item.type}</span><small>{dateLabel(item.date)}</small></div></div>)}</div> : <Empty text={loading ? "Loading your approvals…" : "No submitted items are waiting for review."}/>}</section><section className="panel module-panel"><div className="panel-heading"><div><h2>Your operating modules</h2><p>Access the capabilities enabled for your account</p></div></div><div className="module-list">{[["AR · Receivables","Invoices, receipts and customer balances",ArrowDownLeft,"AR · Receivables"],["AP · Payables","Suppliers and purchasing workflows",ArrowUpRight,"AP · Payables"],["Timesheets","Work logs, hours and approvals",Clock3,"Timesheets"],["Expenses","Claims, review and reimbursement",Receipt,"Expenses"]].map(([title,sub,Icon,target])=><button key={title} onClick={() => setSection(target)}><span className="module-icon"><Icon size={18}/></span><span><b>{title}</b><small>{sub}</small></span><ArrowUpRight size={15}/></button>)}</div></section></div></>;
}


function PreviewOverview({ setSection }) {
  const groups = MODULE_GROUPS.filter(group => group.group !== "Workspace");
  return <div className="preview-overview">
    <section className="preview-intro panel"><div><span className="eyebrow">ASAA PLATFORM MAP</span><h2>One workspace. Every business capability.</h2><p>Browse the complete module structure. This preview contains no sample business records; connect an authorized API session to view live data where integrations exist.</p></div><div className="preview-orbit">A</div></section>
    <div className="module-group-grid">{groups.map(group => <section className="panel module-group-card" key={group.group}><div className="module-group-head"><div><h2>{group.group}</h2><p>{group.items.length} workspaces</p></div><span>{String(group.items.length).padStart(2,"0")}</span></div><div className="module-group-links">{group.items.map(item => <button key={item.name} onClick={() => setSection(item.name)}><span>{item.name}</span><ArrowUpRight size={14}/></button>)}</div></section>)}</div>
  </div>;
}

function ModuleWorkspace({ name, connected, setSection, claims }) {
  const [tab, setTab] = useState("Overview");
  const [filter, setFilter] = useState("");
  const info = MODULE_INFO[name] || { name, description: "ASAA operating workspace.", capabilities: ["Records and ownership", "Workflow and approvals", "Reporting and evidence"], workflows: ["Create and maintain records", "Review pending work", "Track outcomes and evidence"], group: "ASAA Workspace" };
  const related = MODULE_INFO[name]?.group ? MODULE_GROUPS.find(g => g.group === info.group)?.items.filter(x => x.name !== name).slice(0,4) || [] : [];
  const backend = info.backend;
  const backendLabel = backend ? (["ar","ap","hr","onboarding","masterdata","governance","payroll","timesheets","expenses"].includes(backend) ? "API foundation exists · UI integration pending" : "API connection required") : "UI foundation · backend capability not yet connected";
  const tabs = ["Overview","Work queue","Records","Reports","Configuration"];
  const filteredCapabilities = info.capabilities.filter(x => x.toLowerCase().includes(filter.toLowerCase()));
  return <div className="module-workspace">
    <section className="module-hero panel"><div className="module-hero-copy"><div className="module-breadcrumb">{info.group} <span>/</span> Workspace</div><div className="module-title-row"><div><span className="eyebrow">ASAA MODULE WORKSPACE</span><h2>{name}</h2><p>{info.description}</p></div><span className="module-state">{backendLabel}</span></div></div><div className="module-hero-mark"><LayoutDashboard size={28}/></div></section>
    <div className="module-tabbar">{tabs.map(item => <button key={item} className={tab===item?"selected":""} onClick={() => setTab(item)}>{item}</button>)}</div>
    <div className="module-status-strip"><span className={connected?"status-dot online":"status-dot"}/><b>{connected?"Session connected":"Preview only"}</b><span>{connected?"API access remains permission-scoped.":"Connect an authorized session to load records and actions."}</span></div>
    {tab === "Overview" && <>
      <div className="module-kpi-grid"><div className="module-kpi"><small>Records</small><strong>—</strong><span>Live data not loaded</span></div><div className="module-kpi"><small>Pending work</small><strong>—</strong><span>Queue not connected</span></div><div className="module-kpi"><small>In progress</small><strong>—</strong><span>Status not available</span></div><div className="module-kpi"><small>Evidence</small><strong>—</strong><span>Verification not available</span></div></div>
      <div className="module-content-grid"><section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Capabilities</h2><p>What this workspace is designed to manage</p></div><span className="subtle-count">{info.capabilities.length} areas</span></div><div className="module-feature-list">{info.capabilities.map((feature,i)=><div key={feature}><span>{String(i+1).padStart(2,"0")}</span><b>{feature}</b><small>Workspace capability</small></div>)}</div></section><section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Key workflows</h2><p>Typical operating journeys</p></div></div><div className="workflow-steps">{info.workflows.map((step,i)=><div key={step}><span>{i+1}</span><b>{step}</b></div>)}</div></section></div>
    </>}
    {tab === "Work queue" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Work queue</h2><p>Tasks, approvals, exceptions and escalations for this module</p></div><span className="module-state">Awaiting integration</span></div><div className="queue-empty"><ClipboardList size={25}/><b>No live queue connected</b><span>Queue items will appear here when the module's API and workflow permissions are integrated. No placeholder tasks are being counted as real work.</span></div></section>}
    {tab === "Records" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Records</h2><p>Search and browse authoritative records</p></div><span className="subtle-count">Live records unavailable</span></div><div className="module-search"><Search size={16}/><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Filter capability areas in this preview…"/></div><div className="module-record-list">{filteredCapabilities.map(item=><div key={item}><FileText size={16}/><span>{item}</span><span className="record-placeholder">Not connected</span></div>)}</div></section>}
    {tab === "Reports" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Module reporting</h2><p>Metrics and exports will be permission-scoped to source records</p></div></div><div className="report-placeholder-grid"><div><ChartNoAxesCombined/><b>Operational summary</b><span>Waiting for verified data</span></div><div><Activity/><b>Trends & exceptions</b><span>Waiting for verified data</span></div><div><FileCheck2/><b>Evidence report</b><span>Waiting for verified data</span></div></div></section>}
    {tab === "Configuration" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Module configuration</h2><p>Policies and setup are controlled by authorized administrators</p></div></div><div className="config-rows"><div><span>Module</span><b>{name}</b></div><div><span>Domain</span><b>{info.group}</b></div><div><span>Integration state</span><b>{backendLabel}</b></div><div><span>Access principal</span><b>{claims?.sub || "Not connected"}</b></div><div><span>Permission source</span><b>Verified API claims only</b></div></div></section>}
    {related.length>0 && <section className="related-modules"><div><h3>Related workspaces</h3><p>Move between connected capabilities in this domain</p></div><div>{related.map(item=><button key={item.name} onClick={()=>{setSection(item.name);setTab("Overview");}}>{item.name}<ArrowUpRight size={14}/></button>)}</div></section>}
  </div>;
}

function Metric({label,value,note,icon:Icon,tone=""}) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><i className={tone}><Icon size={17}/></i></div><strong>{value}</strong><small>{note}</small></div>; }

function FinanceList({title,subtitle,kind,data,search,setSearch,setModal}) {
  const isAR=kind==="ar"; const rows=isAR?data.invoices:data.suppliers;
  const filtered=rows.filter(row=>JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
  return <section className="panel list-panel"><div className="list-heading"><div><h2>{title}</h2><p>{subtitle}</p></div><button className="btn btn-primary" onClick={()=>setModal(isAR?"customer":"supplier")}><Plus size={15}/>{isAR?"Add customer":"Add supplier"}</button></div><div className="list-tools"><div className="search-box"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder={isAR?"Search invoices…":"Search suppliers…"}/></div><span>{filtered.length} records</span></div><div className="table-wrap"><table><thead><tr>{(isAR?["Invoice","Customer ID","Issue date","Due date","Total","Outstanding","Status"]:["Supplier","Code","Category","Email","Status","Created"]).map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{filtered.map(row=><tr key={row.id}>{isAR?<><td><b>{row.invoice_number || row.id.slice(0,8)}</b><small>{row.currency}</small></td><td className="muted-cell">{row.customer_id.slice(0,10)}</td><td>{dateLabel(row.issue_date)}</td><td>{dateLabel(row.due_date)}</td><td>{money(row.total,row.currency)}</td><td><b>{money(row.outstanding,row.currency)}</b></td><td><Status value={row.status}/></td></>:<><td><b>{row.legal_name}</b><small>{row.trading_name || row.id.slice(0,8)}</small></td><td>{row.supplier_code || "—"}</td><td>{row.category || "—"}</td><td>{row.email || "—"}</td><td><Status value={row.status}/></td><td>{dateLabel(row.created_at)}</td></>}</tr>)}</tbody></table>{!filtered.length&&<Empty text="No records found for this view."/>}</div></section>;
}

function WorkList({title,data,kind,search,setSearch,setModal}) {
  const filtered=data.filter(row=>JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
  return <section className="panel list-panel"><div className="list-heading"><div><h2>{title}</h2><p>{kind==="timesheet"?"Review work periods and submitted hours.":"Track employee claims, decisions and reimbursement records."}</p></div>{kind==="expense"&&<button className="btn btn-primary" onClick={()=>setModal("expense")}><Plus size={15}/>New claim</button>}</div><div className="list-tools"><div className="search-box"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search records…"/></div><span>{filtered.length} records</span></div><div className="table-wrap"><table><thead><tr>{(kind==="timesheet"?["Employee","Period","Hours","Status","Reviewed by"]:["Description","Employee","Date","Category","Amount","Status"]).map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{filtered.map(row=><tr key={row.id}>{kind==="timesheet"?<><td><b>{row.employee_reference||row.employee_subject}</b></td><td>{dateLabel(row.period_start)} – {dateLabel(row.period_end)}</td><td>{row.total_hours} h</td><td><Status value={row.status}/></td><td>{row.reviewed_by||"—"}</td></>:<><td><b>{row.description}</b><small>{row.merchant||row.receipt_reference||"—"}</small></td><td>{row.employee_subject}</td><td>{dateLabel(row.expense_date)}</td><td>{row.category_code}</td><td>{money(row.amount,row.currency)}</td><td><Status value={row.status}/></td></>}</tr>)}</tbody></table>{!filtered.length&&<Empty text="No records found for this view."/>}</div></section>;
}

function Status({value}) { const key=(value||"unknown").toLowerCase().replaceAll(" ","-"); return <span className={`status status-${key}`}>{value||"Unknown"}</span>; }
function Empty({text}) { return <div className="empty-state"><div><FileText size={20}/></div>{text}</div>; }

function Governance({claims}) {
  const perms=Array.isArray(claims.permissions)?claims.permissions:[];
  return <div className="settings-grid"><section className="panel info-panel"><div className="panel-heading"><div><h2>Executive identity</h2><p>Current session claims, as provided by the identity provider</p></div><ShieldCheck size={18}/></div><div className="identity-line"><div className="large-avatar">AD</div><div><b>{claims.name||claims.sub||"Authenticated user"}</b><small>Founder · CEO · Director · Current responsibilities (workspace designation)</small></div></div><div className="data-line"><span>Organization scope</span><b>{claims.org_id||"Not present"}</b></div><div className="data-line"><span>Token issuer</span><b>{claims.iss||"Not present"}</b></div><div className="data-line"><span>Token expiry</span><b>{claims.exp?new Date(claims.exp*1000).toLocaleString():"Not present"}</b></div></section><section className="panel info-panel"><div className="panel-heading"><div><h2>Effective permissions</h2><p>Authorization is enforced by the API, not by UI labels</p></div><ShieldCheck size={18}/></div>{perms.length?<div className="permission-list">{perms.map(p=><span key={p}><Check size={13}/>{p}</span>)}</div>:<Empty text="No permission claims were exposed in this session."/>}</section></div>;
}

function Reports({data,stats}) { return <div className="metric-grid"><Metric label="AR outstanding" value={money(stats.outstanding)} note={`${data.invoices.length} invoices`} icon={Landmark}/><Metric label="Receipts recorded" value={data.receipts.length} note="AR receipt records" icon={Wallet}/><Metric label="Timesheets" value={data.timesheets.length} note="Work periods recorded" icon={Clock3}/><Metric label="Expense claims" value={data.expenses.length} note="Claims recorded" icon={Receipt}/></div>; }
function SettingsPanel({apiBase,setApiBase,claims,openConnection}) { return <div className="settings-grid"><section className="panel info-panel"><div className="panel-heading"><div><h2>Workspace connection</h2><p>API endpoint and session controls</p></div><Settings2 size={18}/></div><div className="data-line"><span>API endpoint</span><b>{apiBase}</b></div><div className="data-line"><span>Organization</span><b>{claims.org_id||"—"}</b></div><button className="btn btn-quiet" onClick={openConnection}>Manage connection</button></section><section className="panel info-panel"><div className="panel-heading"><div><h2>Install on your devices</h2><p>One responsive app across your screens</p></div><Smartphone size={18}/></div><div className="device-row"><Monitor/> Desktop / laptop <span>Browser or installable PWA</span></div><div className="device-row"><Smartphone/> Mobile <span>Add to Home Screen</span></div><div className="device-row"><Laptop/> Tablet <span>Responsive layout</span></div><small className="field-help">The app shell can be cached for offline launch. Financial records and API data are never cached by the service worker.</small></section></div>; }

function RecordForm({kind,onCancel,onSave}) {
  const [form,setForm]=useState({}); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const fields=kind==="expense"?[["description","Description","text"],["category_code","Category code","text"],["merchant","Merchant","text"],["expense_date","Expense date","date"],["amount","Amount","number"],["currency","Currency (e.g. INR)","text"],["receipt_reference","Receipt reference (optional)","text"],["project_reference","Project reference (optional)","text"]]:kind==="customer"?[["legal_name","Customer legal name","text"],["trading_name","Trading name (optional)","text"],["email","Email (optional)","email"],["phone","Phone (optional)","text"]]:[["legal_name","Supplier legal name","text"],["trading_name","Trading name (optional)","text"],["email","Email (optional)","email"],["phone","Phone (optional)","text"],["category","Category (optional)","text"]];
  const submit=async e=>{e.preventDefault();setBusy(true);setError("");try{const payload={...form};if(kind==="expense"){payload.amount=Number(payload.amount);payload.currency=(payload.currency||"INR").toUpperCase();}await onSave(kind,payload);}catch(e){setError(e.message||"Could not save this record.");}finally{setBusy(false);}};
  return <form className="record-form" onSubmit={submit}>{fields.map(([key,label,type])=><label key={key}>{label}<input required={!label.includes("optional")} type={type} value={form[key]||""} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}{error&&<div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={onCancel}>Cancel</button><button className="btn btn-primary" disabled={busy}>{busy?"Saving…":"Save record"}</button></div></form>;
}

function ConnectionForm({apiBase,setApiBase,tokenInput,setTokenInput,connect,connected,ssoConfigured,onSsoSignIn,ssoError}) { return <div className="record-form">{ssoConfigured && <button className="btn btn-primary" onClick={onSsoSignIn}>Sign in with SSO</button>}{ssoError && <div className="form-error">{ssoError}</div>}<label>API endpoint<input value={apiBase} onChange={e=>setApiBase(e.target.value)}/></label><label>Access token<textarea rows="4" value={tokenInput} onChange={e=>setTokenInput(e.target.value)} placeholder="Paste an identity-provider token"/></label><small className="field-help">The token is held in memory only. Disconnect or refresh to clear it.</small><div className="modal-actions"><span className="field-help">{connected?"API session active":"No active API session"}</span><button className="btn btn-primary" onClick={connect}>Connect</button></div></div>; }
function Modal({title,onClose,children}) { return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal"><div className="modal-heading"><h2>{title}</h2><button className="icon-btn" onClick={onClose}><X size={18}/></button></div>{children}</div></div>; }
function sectionDescription(name) { return MODULE_INFO[name]?.description || ({ "AR · Receivables":"Manage customers, invoices, incoming receipts and balances.", "AP · Payables":"Manage suppliers and the purchasing-to-payment lifecycle.", "Timesheets":"Track work periods, hours and independent review.", "Expenses":"Capture expense claims and track approvals and reimbursement.", "Governance":"Review decisions, delegations and authority.", "Reports":"A consolidated view of current operating records.", "Settings":"Manage your workspace connection and device experience." })[name] || "Manage your ASAA workspace."; }

export default App;