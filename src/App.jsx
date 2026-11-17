import ProcurementWorkspace from "./ProcurementWorkspace.jsx";
import SupplierWorkspace from "./SupplierWorkspace.jsx";
import ReceivablesWorkspace from "./ReceivablesWorkspace.jsx";
import WorkforceFinanceWorkspace from "./WorkforceFinanceWorkspace.jsx";
import AdministrationWorkspace from "./AdministrationWorkspace.jsx";
import PeopleWorkspace from "./PeopleWorkspace.jsx";
import PayrollWorkspace from "./PayrollWorkspace.jsx";
import { MODULE_GROUPS, REGISTER_WORKSPACES, ROUTED_WORKSPACES } from "./workspaces/registry.js";
import RegisterWorkspace from "./RegisterWorkspace.jsx";
import { AuditTrailWorkspace, BackupRecoveryWorkspace, EcosystemStatusPanel, GovernanceWorkspace, IntegrationEventsPanel, LeavePolicyPanel, NotificationsWorkspace, ReportsWorkspace } from "./PlatformWorkspaces.jsx";
import { completeSsoSignIn, isSsoConfigured, startSsoSignIn } from "./identity/oidc.js";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowDownLeft, ArrowUpRight, Bell, BriefcaseBusiness, Building2, CalendarDays,
  Check, ChevronDown, CircleHelp, Clock3, Command, CreditCard, FileCheck2, FileText,
  Gauge, LayoutDashboard, Menu, Plus, Search, Settings2, ShieldCheck, Users, Wallet,
  X, RefreshCw, LogOut, Smartphone, Monitor, Laptop, Receipt, ChartNoAxesCombined,
  Landmark, ClipboardList, CircleDollarSign, UserRound
} from "lucide-react";

const EMPTY_DATA = { suppliers: [], customers: [], invoices: [], receipts: [], timesheets: [], expenses: [], purchaseRequests: [] };
const API_DEFAULT = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";
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
  const [data, setData] = useState(EMPTY_DATA);
  const [modal, setModal] = useState("");
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
        setData(EMPTY_DATA);
      }
      const failure = new Error(typeof body.detail === "string" ? body.detail : body.detail ? JSON.stringify(body.detail) : `Request failed (${response.status})`);
      failure.status = response.status;
      throw failure;
    }
    return response.status === 204 ? null : response.json();
  };

  const refresh = async () => {
    if (!token) return;
    setLoading(true); setError("");
    const permittedJobs = [
      ["suppliers", "/api/v1/ap/suppliers", "supplier:read"],
      ["customers", "/api/v1/ar/customers", "ar:customer:read"],
      ["invoices", "/api/v1/ar/invoices", "ar:invoice:read"],
      ["receipts", "/api/v1/ar/receipts", "ar:receipt:read"],
      ["timesheets", "/api/v1/workforce-finance/timesheets", "tms:timesheet:read"],
      ["expenses", "/api/v1/workforce-finance/expenses", "expense:claim:read"],
      ["purchaseRequests", "/api/v1/ap/purchase-requests", "procurement:request:read"]
    ];
    const granted = new Set(Array.isArray(claims.permissions) ? claims.permissions : []);
    const jobs = permittedJobs.filter(([, , permission]) => granted.has(permission)).map(([key, path]) => [key, path]);
    let unauthorized = false;
    // Confirm the token is actually accepted by the API before reporting a connected session.
    try { await api("/api/v1/me"); }
    catch (e) { if (e.status === 401) unauthorized = true; }
    if (unauthorized) { setLoading(false); setError("The access token was not accepted by the API."); return; }
    const results = await Promise.all(jobs.map(async ([key, path]) => {
      try { return [key, await api(path)]; }
      catch (e) { if (e.status === 401) unauthorized = true; return [key, [], e.message]; }
    }));
    // A 401 already cleared the session in api(); do not report a connected state for an expired token.
    if (unauthorized) { setLoading(false); return; }
    const next = Object.fromEntries(results.map(([key, value]) => [key, Array.isArray(value) ? value : []]));
    const failures = results.filter(([, , message]) => message).map(([key, , message]) => `${key}: ${message}`);
    // Only permitted areas are fetched; keep every collection defined so partially-permitted sessions render.
    setData({ ...EMPTY_DATA, ...next }); setConnected(true);
    if (jobs.length > 0 && failures.length === jobs.length) setError("The API could not be reached or this account has no read permissions. Check the API URL and access permissions.");
    else if (failures.length) setError(`Some areas are unavailable for this account: ${failures.join(" · ")}`);
    setLoading(false);
  };

  const connect = async () => {
    if (!tokenInput.trim()) { setError("Enter an access token issued by the configured identity provider."); return; }
    setToken(tokenInput.trim()); setError(""); setLoading(true);
  };
  // refresh closes over the current token/claims; it must only re-run when the token changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
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


  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById("main-content")?.focus(); }}>Skip to main content</a>
    <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-mark">A</div><div><strong>ASAA</strong><span>OPERATING PLATFORM</span></div><button className="icon-btn sidebar-close" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={18}/></button></div>
      <div className="workspace-switch"><div className="workspace-avatar">A</div><div><b>ASAA Workspace</b><small>Founder workspace</small></div><ChevronDown size={15}/></div>
      <div className="sidebar-search"><Search size={15}/><input value={navSearch} onChange={e=>setNavSearch(e.target.value)} placeholder="Find a module…"/>{navSearch && <button onClick={()=>setNavSearch("")} aria-label="Clear module search"><X size={13}/></button>}</div>
      <nav>
        {NAV.map(group => <div className="nav-group" key={group.group}><small className="nav-caption">{group.group}</small>{group.items.filter(([name])=>name.toLowerCase().includes(navSearch.toLowerCase())).map(([name, Icon]) => <button key={name} className={`nav-item ${section === name ? "active" : ""}`} onClick={() => { setSection(name); setMobileNav(false); }}><Icon size={17}/><span>{name}</span>{name === "Expenses" && stats.pendingExpenses > 0 && token && <i>{stats.pendingExpenses}</i>}</button>)}</div>)}
      </nav>
      <div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={16}/><span>Secure workspace<br/><small>Access controlled by permissions</small></span></div><button className="nav-item" onClick={() => setModal("connection")}><Settings2 size={17}/>Connection settings</button></div>
      <div className="sidebar-user"><div className="user-avatar">AD</div><div><b>{claims.name || (token ? "ASAA Administrator" : "Preview visitor")}</b><small>{token ? "Founder · CEO · Director · Current responsibilities" : "Unauthenticated UI preview"}</small></div><button className="icon-btn" title="Sign out" onClick={() => { setToken(""); setTokenInput(""); setConnected(false); setData(EMPTY_DATA); }}><LogOut size={16}/></button></div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <button className="icon-btn mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={20}/></button>
        <div className="crumb"><span>ASAA</span><b>/</b><strong>{section}</strong></div>
        <div className="top-actions"><div className="system-status"><span className={connected ? "status-dot online" : "status-dot"}/>{connected ? "API connected" : "Not connected"}</div><button className="icon-btn" title="Help"><CircleHelp size={18}/></button><button className="icon-btn notification-btn" title="Notifications"><Bell size={18}/><i/></button><div className="top-avatar">{token ? "AD" : "PV"}</div></div>
      </header>

      <div className="content" id="main-content" tabIndex={-1}>
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
          {["People directory","Employment lifecycle","Onboarding","Offboarding","Leave management","Employee assets"].includes(section) && <PeopleWorkspace name={section} api={api} claims={claims} connected={!!token} onChanged={refresh}/>}
          {section === "Budgets & forecasting" && <ReportsWorkspace name="Budget versus actuals" only={["budget_variance"]} api={api} connected={!!token}/>}
          {section === "Leave management" && <LeavePolicyPanel api={api} claims={claims} connected={!!token}/>}
          {section === "Compensation & payroll" && <PayrollWorkspace api={api} claims={claims} connected={!!token} onChanged={refresh}/>}
                    {["Organization & entities","Departments & teams","Master data","Identity & access","Access reviews"].includes(section) && <AdministrationWorkspace name={section} api={api} claims={claims} connected={!!token} onChanged={refresh}/>}
          {section === "Reports & dashboards" && <ReportsWorkspace api={api} connected={!!token}/>}
          {section === "Financial reporting" && <ReportsWorkspace name="Financial reporting" only={["receivables", "customers", "receipts", "suppliers", "procurement", "expenses"]} api={api} connected={!!token}/>}
          {section === "Accounting & reconciliation" && <ReportsWorkspace name="Accounting & reconciliation" only={["reconciliation"]} api={api} connected={!!token}/>}
          {section === "Cash flow & treasury" && <ReportsWorkspace name="Cash flow & treasury" only={["cash_outlook"]} api={api} connected={!!token}/>}
          {section === "Payroll accounting" && <ReportsWorkspace name="Payroll accounting" only={["payroll_accounting"]} api={api} connected={!!token}/>}
          {section === "Backup & recovery" && <><BackupRecoveryWorkspace api={api} claims={claims} connected={!!token}/><EcosystemStatusPanel api={api} claims={claims} connected={!!token}/><IntegrationEventsPanel api={api} claims={claims} connected={!!token}/></>}
          {section === "Audit trail" && <AuditTrailWorkspace api={api} claims={claims} connected={!!token}/>}
          {section === "Notifications & reminders" && <NotificationsWorkspace api={api} claims={claims} connected={!!token}/>}
          {section === "Governance" && <GovernanceWorkspace api={api} claims={claims} connected={!!token}/>}
          {REGISTER_WORKSPACES[section] && <RegisterWorkspace key={section} name={section} types={REGISTER_WORKSPACES[section]} renewals={section === "Contracts & renewals"} api={api} claims={claims} connected={!!token} onChanged={refresh}/>}
          {section === "Settings" && <SettingsPanel apiBase={apiBase} claims={claims} openConnection={() => setModal("connection")}/>}
          {!ROUTED_WORKSPACES.includes(section) && <ModuleWorkspace name={section} connected={!!token} setSection={setSection} claims={claims}/>}
          <footer className="page-footer"><span>ASAA · Enterprise Operating Platform</span><span>Secure by design <ShieldCheck size={13}/></span></footer>
        </>}
      </div>
    </main>

    {modal && <Modal title={modal === "connection" ? "API connection" : modal === "expense" ? "New expense claim" : modal === "customer" ? "Add customer" : modal === "supplier" ? "Add supplier" : "Create a record"} onClose={() => setModal("")}>
      {modal === "connection" ? <ConnectionForm apiBase={apiBase} setApiBase={setApiBase} tokenInput={tokenInput} setTokenInput={setTokenInput} connect={connect} connected={connected} ssoConfigured={isSsoConfigured} onSsoSignIn={signInSso} ssoError={ssoError}/> :
       modal === "quick" ? <div className="quick-grid">{[["expense","Expense claim",Receipt],["customer","Customer",Users],["supplier","Supplier",Building2]].map(([key,label,Icon]) => <button className="quick-option" key={key} onClick={() => setModal(key)}><Icon size={20}/><b>{label}</b><span>Create a new {label.toLowerCase()}</span></button>)}</div> :
       <RecordForm kind={modal} onCancel={() => setModal("")} onSave={createRecord}/>}
    </Modal>}
    {toast && <div className="toast" role="status" aria-live="polite"><Check size={16}/>{toast}</div>}
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
    {tab === "Work queue" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Work queue</h2><p>Tasks, approvals, exceptions and escalations for this module</p></div><span className="module-state">Awaiting integration</span></div><div className="queue-empty"><ClipboardList size={25}/><b>No live queue connected</b><span>Queue items will appear here when the module&apos;s API and workflow permissions are integrated. No placeholder tasks are being counted as real work.</span></div></section>}
    {tab === "Records" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Records</h2><p>Search and browse authoritative records</p></div><span className="subtle-count">Live records unavailable</span></div><div className="module-search"><Search size={16}/><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Filter capability areas in this preview…"/></div><div className="module-record-list">{filteredCapabilities.map(item=><div key={item}><FileText size={16}/><span>{item}</span><span className="record-placeholder">Not connected</span></div>)}</div></section>}
    {tab === "Reports" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Module reporting</h2><p>Metrics and exports will be permission-scoped to source records</p></div></div><div className="report-placeholder-grid"><div><ChartNoAxesCombined/><b>Operational summary</b><span>Waiting for verified data</span></div><div><Activity/><b>Trends & exceptions</b><span>Waiting for verified data</span></div><div><FileCheck2/><b>Evidence report</b><span>Waiting for verified data</span></div></div></section>}
    {tab === "Configuration" && <section className="panel module-detail-panel"><div className="panel-heading"><div><h2>Module configuration</h2><p>Policies and setup are controlled by authorized administrators</p></div></div><div className="config-rows"><div><span>Module</span><b>{name}</b></div><div><span>Domain</span><b>{info.group}</b></div><div><span>Integration state</span><b>{backendLabel}</b></div><div><span>Access principal</span><b>{claims?.sub || "Not connected"}</b></div><div><span>Permission source</span><b>Verified API claims only</b></div></div></section>}
    {related.length>0 && <section className="related-modules"><div><h3>Related workspaces</h3><p>Move between connected capabilities in this domain</p></div><div>{related.map(item=><button key={item.name} onClick={()=>{setSection(item.name);setTab("Overview");}}>{item.name}<ArrowUpRight size={14}/></button>)}</div></section>}
  </div>;
}

function Metric({label,value,note,icon:Icon,tone=""}) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><i className={tone}><Icon size={17}/></i></div><strong>{value}</strong><small>{note}</small></div>; }



function Empty({text}) { return <div className="empty-state"><div><FileText size={20}/></div>{text}</div>; }


function SettingsPanel({apiBase,claims,openConnection}) { return <div className="settings-grid"><section className="panel info-panel"><div className="panel-heading"><div><h2>Workspace connection</h2><p>API endpoint and session controls</p></div><Settings2 size={18}/></div><div className="data-line"><span>API endpoint</span><b>{apiBase}</b></div><div className="data-line"><span>Organization</span><b>{claims.org_id||"—"}</b></div><button className="btn btn-quiet" onClick={openConnection}>Manage connection</button></section><section className="panel info-panel"><div className="panel-heading"><div><h2>Install on your devices</h2><p>One responsive app across your screens</p></div><Smartphone size={18}/></div><div className="device-row"><Monitor/> Desktop / laptop <span>Browser or installable PWA</span></div><div className="device-row"><Smartphone/> Mobile <span>Add to Home Screen</span></div><div className="device-row"><Laptop/> Tablet <span>Responsive layout</span></div><small className="field-help">The app shell can be cached for offline launch. Financial records and API data are never cached by the service worker.</small></section></div>; }

function RecordForm({kind,onCancel,onSave}) {
  const [form,setForm]=useState({}); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const fields=kind==="expense"?[["description","Description","text"],["category_code","Category code","text"],["merchant","Merchant","text"],["expense_date","Expense date","date"],["amount","Amount","number"],["currency","Currency (e.g. INR)","text"],["receipt_reference","Receipt reference (optional)","text"],["project_reference","Project reference (optional)","text"]]:kind==="customer"?[["legal_name","Customer legal name","text"],["trading_name","Trading name (optional)","text"],["email","Email (optional)","email"],["phone","Phone (optional)","text"]]:[["legal_name","Supplier legal name","text"],["trading_name","Trading name (optional)","text"],["email","Email (optional)","email"],["phone","Phone (optional)","text"],["category","Category (optional)","text"]];
  const submit=async e=>{e.preventDefault();setBusy(true);setError("");try{const payload={...form};if(kind==="expense"){payload.amount=Number(payload.amount);payload.currency=(payload.currency||"INR").toUpperCase();}await onSave(kind,payload);}catch(e){setError(e.message||"Could not save this record.");}finally{setBusy(false);}};
  return <form className="record-form" onSubmit={submit}>{fields.map(([key,label,type])=><label key={key}>{label}<input required={!label.includes("optional")} type={type} value={form[key]||""} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}{error&&<div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={onCancel}>Cancel</button><button className="btn btn-primary" disabled={busy}>{busy?"Saving…":"Save record"}</button></div></form>;
}

function ConnectionForm({apiBase,setApiBase,tokenInput,setTokenInput,connect,connected,ssoConfigured,onSsoSignIn,ssoError}) { return <div className="record-form">{ssoConfigured && <button className="btn btn-primary" onClick={onSsoSignIn}>Sign in with SSO</button>}{ssoError && <div className="form-error">{ssoError}</div>}<label>API endpoint<input value={apiBase} onChange={e=>setApiBase(e.target.value)}/></label><label>Access token<textarea rows="4" value={tokenInput} onChange={e=>setTokenInput(e.target.value)} placeholder="Paste an identity-provider token"/></label><small className="field-help">The token is held in memory only. Disconnect or refresh to clear it.</small><div className="modal-actions"><span className="field-help">{connected?"API session active":"No active API session"}</span><button className="btn btn-primary" onClick={connect}>Connect</button></div></div>; }
function Modal({title,onClose,children}) {
  const dialogRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const opener = document.activeElement;
    dialogRef.current?.focus();
    const onKey = e => {
      if (e.key === "Escape") { closeRef.current(); return; }
      if (e.key !== "Tab" || !dialogRef.current) return;
      // Keep keyboard focus inside the modal dialog.
      const items = [...dialogRef.current.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')];
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); if (opener instanceof HTMLElement) opener.focus(); };
  }, []);
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal" ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-btn" aria-label="Close dialog" onClick={onClose}><X size={18}/></button></div>{children}</div></div>;
}
function sectionDescription(name) { return MODULE_INFO[name]?.description || ({ "AR · Receivables":"Manage customers, invoices, incoming receipts and balances.", "AP · Payables":"Manage suppliers and the purchasing-to-payment lifecycle.", "Timesheets":"Track work periods, hours and independent review.", "Expenses":"Capture expense claims and track approvals and reimbursement.", "Governance":"Review decisions, delegations and authority.", "Reports":"A consolidated view of current operating records.", "Settings":"Manage your workspace connection and device experience." })[name] || "Manage your ASAA workspace."; }

export default App;