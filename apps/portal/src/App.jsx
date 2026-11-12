import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownLeft, ArrowUpRight, Bell, BriefcaseBusiness, Building2, CalendarDays,
  Check, ChevronDown, CircleHelp, Clock3, Command, CreditCard, FileCheck2, FileText,
  Gauge, LayoutDashboard, Menu, Plus, Search, Settings2, ShieldCheck, Users, Wallet,
  X, RefreshCw, LogOut, Smartphone, Monitor, Laptop, Receipt, ChartNoAxesCombined,
  Landmark, ClipboardList, CircleDollarSign, UserRound
} from "lucide-react";

const API_DEFAULT = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const NAV = [
  { group: "Workspace", items: [
    ["Overview", LayoutDashboard], ["AR · Receivables", ArrowDownLeft], ["AP · Payables", ArrowUpRight]
  ]},
  { group: "People & Work", items: [
    ["Timesheets", Clock3], ["Expenses", Receipt]
  ]},
  { group: "Control centre", items: [
    ["Governance", ShieldCheck], ["Reports", ChartNoAxesCombined], ["Settings", Settings2]
  ]}
];
const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value || 0));
const dateLabel = value => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const decodeClaims = token => {
  try { return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); } catch { return {}; }
};

function App() {
  const [section, setSection] = useState("Overview");
  const [mobileNav, setMobileNav] = useState(false);
  const [apiBase, setApiBase] = useState(API_DEFAULT);
  const [tokenInput, setTokenInput] = useState("");
  const [token, setToken] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState({ suppliers: [], customers: [], invoices: [], receipts: [], timesheets: [], expenses: [] });
  const [modal, setModal] = useState("");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState("");
  const claims = useMemo(() => decodeClaims(token), [token]);

  const api = async (path, options = {}) => {
    const response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(options.headers || {}) }
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${response.status})`);
    }
    return response.status === 204 ? null : response.json();
  };

  const refresh = async () => {
    if (!token) return;
    setLoading(true); setError("");
    const jobs = [
      ["suppliers", "/api/v1/ap/suppliers"], ["customers", "/api/v1/ar/customers"],
      ["invoices", "/api/v1/ar/invoices"], ["receipts", "/api/v1/ar/receipts"],
      ["timesheets", "/api/v1/workforce-finance/timesheets"], ["expenses", "/api/v1/workforce-finance/expenses"]
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
      <nav>
        {NAV.map(group => <div className="nav-group" key={group.group}><small className="nav-caption">{group.group}</small>{group.items.map(([name, Icon]) => <button key={name} className={`nav-item ${section === name ? "active" : ""}`} onClick={() => { setSection(name); setMobileNav(false); }}><Icon size={17}/><span>{name}</span>{name === "Expenses" && stats.pendingExpenses > 0 && <i>{stats.pendingExpenses}</i>}</button>)}</div>)}
      </nav>
      <div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={16}/><span>Secure workspace<br/><small>Access controlled by permissions</small></span></div><button className="nav-item" onClick={() => setModal("connection")}><Settings2 size={17}/>Connection settings</button></div>
      <div className="sidebar-user"><div className="user-avatar">AD</div><div><b>{claims.name || "ASAA Administrator"}</b><small>Founder · CEO · Director · Current responsibilities</small></div><button className="icon-btn" title="Sign out" onClick={() => { setToken(""); setTokenInput(""); setConnected(false); setData({ suppliers: [], customers: [], invoices: [], receipts: [], timesheets: [], expenses: [] }); }}><LogOut size={16}/></button></div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <button className="icon-btn mobile-menu" onClick={() => setMobileNav(true)}><Menu size={20}/></button>
        <div className="crumb"><span>ASAA</span><b>/</b><strong>{section}</strong></div>
        <div className="top-actions"><div className="system-status"><span className={connected ? "status-dot online" : "status-dot"}/>{connected ? "API connected" : "Not connected"}</div><button className="icon-btn" title="Help"><CircleHelp size={18}/></button><button className="icon-btn notification-btn" title="Notifications"><Bell size={18}/><i/></button><div className="top-avatar">AD</div></div>
      </header>

      <div className="content">
        {!token ? <ConnectScreen apiBase={apiBase} setApiBase={setApiBase} tokenInput={tokenInput} setTokenInput={setTokenInput} connect={connect} error={error}/> :
        <>
          <div className="welcome-row"><div><div className="eyebrow">{new Date().toLocaleDateString("en-IN", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).toUpperCase()} · EXECUTIVE OVERVIEW</div><h1>{section === "Overview" ? "Good afternoon." : section}</h1><p>{section === "Overview" ? "Your company, operations and financial position at a glance." : sectionDescription(section)}</p></div><div className="welcome-actions"><button className="btn btn-quiet" onClick={refresh} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""}/> Refresh</button><button className="btn btn-primary" onClick={() => setModal("quick")}><Plus size={16}/> Create new</button></div></div>
          {error && <div className="notice"><Activity size={16}/><span>{error}</span></div>}
          {section === "Overview" && <Overview data={data} stats={stats} loading={loading} setSection={setSection} setModal={setModal}/>}
          {section === "AR · Receivables" && <FinanceList title="Accounts receivable" subtitle="Customers, issued invoices and incoming receipts." kind="ar" data={data} search={search} setSearch={setSearch} setModal={setModal}/>}
          {section === "AP · Payables" && <FinanceList title="Accounts payable" subtitle="Supplier directory and payable operations (invoice processing is a planned increment)." kind="ap" data={data} search={search} setSearch={setSearch} setModal={setModal}/>}
          {section === "Timesheets" && <WorkList title="Time & timesheet management" data={data.timesheets} kind="timesheet" search={search} setSearch={setSearch}/>}
          {section === "Expenses" && <WorkList title="Expense management" data={data.expenses} kind="expense" search={search} setSearch={setSearch} setModal={setModal}/>}
          {section === "Governance" && <Governance claims={claims}/>}
          {section === "Reports" && <Reports data={data} stats={stats}/>}
          {section === "Settings" && <SettingsPanel apiBase={apiBase} setApiBase={setApiBase} claims={claims} openConnection={() => setModal("connection")}/>}
          <footer className="page-footer"><span>ASAA · Enterprise Operating Platform</span><span>Secure by design <ShieldCheck size={13}/></span></footer>
        </>}
      </div>
    </main>

    {modal && <Modal title={modal === "connection" ? "API connection" : modal === "expense" ? "New expense claim" : modal === "customer" ? "Add customer" : modal === "supplier" ? "Add supplier" : "Create a record"} onClose={() => setModal("")}>
      {modal === "connection" ? <ConnectionForm apiBase={apiBase} setApiBase={setApiBase} tokenInput={tokenInput} setTokenInput={setTokenInput} connect={connect} connected={connected}/> :
       modal === "quick" ? <div className="quick-grid">{[["expense","Expense claim",Receipt],["customer","Customer",Users],["supplier","Supplier",Building2]].map(([key,label,Icon]) => <button className="quick-option" key={key} onClick={() => setModal(key)}><Icon size={20}/><b>{label}</b><span>Create a new {label.toLowerCase()}</span></button>)}</div> :
       <RecordForm kind={modal} onCancel={() => setModal("")} onSave={createRecord}/>}
    </Modal>}
    {toast && <div className="toast"><Check size={16}/>{toast}</div>}
  </div>;
}

function ConnectScreen({ apiBase, setApiBase, tokenInput, setTokenInput, connect, error }) {
  return <div className="connect-layout"><div className="connect-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="connect-emblem">A</div><div className="art-label"><span/> ONE WORKSPACE. EVERYWHERE.</div></div><div className="connect-card"><div className="eyebrow">ASAA · EXECUTIVE ACCESS</div><h1>Welcome back.</h1><p>Connect to your secure ASAA workspace to manage finance, people and operations from any device.</p><label>API endpoint</label><input value={apiBase} onChange={e => setApiBase(e.target.value)} placeholder="https://api.your-domain.com"/><label>Identity access token</label><textarea rows="3" value={tokenInput} onChange={e => setTokenInput(e.target.value)} placeholder="Paste a valid access token from your identity provider"/><small className="field-help">Your token stays in memory for this session and is not saved to this device.</small>{error && <div className="form-error">{error}</div>}<button className="btn btn-primary btn-full" onClick={connect}>Connect to ASAA <ArrowUpRight size={16}/></button><div className="connect-security"><ShieldCheck size={16}/> Verified by your configured identity provider</div><div className="connect-foot">Desktop · Tablet · Mobile · Installable app</div></div></div>;
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

function Metric({label,value,note,icon:Icon,tone=""}) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><i className={tone}><Icon size={17}/></i></div><strong>{value}</strong><small>{note}</small></div>; }

function FinanceList({title,subtitle,kind,data,search,setSearch,setModal}) {
  const isAR=kind==="ar"; const rows=isAR?data.invoices:data.suppliers;
  const filtered=rows.filter(row=>JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
  return <section className="panel list-panel"><div className="list-heading"><div><h2>{title}</h2><p>{subtitle}</p></div><button className="btn btn-primary" onClick={()=>setModal(isAR?"customer":"supplier")}><Plus size={15}/>{isAR?"Add customer":"Add supplier"}</button></div><div className="list-tools"><div className="search-box"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder={isAR?"Search invoices…":"Search suppliers…"}/></div><span>{filtered.length} records</span></div><div className="table-wrap"><table><thead><tr>{(isAR?["Invoice","Customer ID","Issue date","Due date","Total","Outstanding","Status"]:["Supplier","Code","Category","Email","Status","Created"]).map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{filtered.map(row=><tr key={row.id}>{isAR?<><td><b>{row.invoice_number || row.id.slice(0,8)}</b><small>{row.currency}</small></td><td className="muted-cell">{row.customer_id.slice(0,10)}</td><td>{dateLabel(row.issue_date)}</td><td>{dateLabel(row.due_date)}</td><td>{money(row.total,row.currency)}</td><td><b>{money(row.outstanding,row.currency)}</b></td><td><Status value={row.status}/></td></>:<><td><b>{row.legal_name}</b><small>{row.trading_name || row.id.slice(0,8)}</small></td><td>{row.supplier_code || "—"}</td><td>{row.category || "—"}</td><td>{row.email || "—"}</td><td><Status value={row.status}/></td><td>{dateLabel(row.created_at)}</td></>}</tr>)}</tbody></table>{!filtered.length&&<Empty text="No records found for this view."/>}</div></section>;
}

function WorkList({title,data,kind,search,setSearch,setModal}) {
  const filtered=data.filter(row=>JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
  return <section className="panel list-panel"><div className="list-heading"><div><h2>{title}</h2><p>{kind==="timesheet"?"Review work periods and submitted hours.":"Track employee claims, decisions and reimbursement records."}</p></div>{kind==="expense"&&<button className="btn btn-primary" onClick={()=>setModal("expense")}><Plus size={15}/>New claim</button>}</div><div className="list-tools"><div className="search-box"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search records…"/></div><span>{filtered.length} records</span></div><div className="table-wrap"><table><thead><tr>{(kind==="timesheet"?["Employee","Period","Hours","Status","Reviewed by"]:["Description","Employee","Date","Category","Amount","Status"]).map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{filtered.map(row=><tr key={row.id}>{kind==="timesheet"?<><td><b>{row.employee_reference||row.employee_subject}</b></td><td>{dateLabel(row.period_start)} – {dateLabel(row.period_end)}</td><td>{row.total_hours} h</td><td><Status value={row.status}/></td><td>{row.reviewed_by||"—"}</td></>:<><td><b>{row.description}</b><small>{row.merchant||row.receipt_reference||"—"}</small></td><td>{row.employee_subject}</td><td>{dateLabel(row.expense_date)}</td><td>{row.category_code}</td><td>{money(row.amount,row.currency)}</td><td><Status value={row.status}/></td></>}</tr>)}</tbody></table>{!filtered.length&&<Empty text="No records found for this view."/></div></section>;
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

function ConnectionForm({apiBase,setApiBase,tokenInput,setTokenInput,connect,connected}) { return <div className="record-form"><label>API endpoint<input value={apiBase} onChange={e=>setApiBase(e.target.value)}/></label><label>Access token<textarea rows="4" value={tokenInput} onChange={e=>setTokenInput(e.target.value)} placeholder="Paste an identity-provider token"/></label><small className="field-help">The token is held in memory only. Disconnect or refresh to clear it.</small><div className="modal-actions"><span className="field-help">{connected?"API session active":"No active API session"}</span><button className="btn btn-primary" onClick={connect}>Connect</button></div></div>; }
function Modal({title,onClose,children}) { return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="modal"><div className="modal-heading"><h2>{title}</h2><button className="icon-btn" onClick={onClose}><X size={18}/></button></div>{children}</div></div>; }
function sectionDescription(name) { return ({ "AR · Receivables":"Manage customers, invoices, incoming receipts and balances.", "AP · Payables":"Manage suppliers and the purchasing-to-payment lifecycle.", "Timesheets":"Track work periods, hours and independent review.", "Expenses":"Capture expense claims and track approvals and reimbursement.", "Governance":"Review your identity, authority and effective access.", "Reports":"A consolidated view of current operating records.", "Settings":"Manage your workspace connection and device experience." })[name]||"Manage your ASAA workspace."; }

export default App;