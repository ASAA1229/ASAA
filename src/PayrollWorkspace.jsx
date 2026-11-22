import { useCallback, useEffect, useRef, useState } from "react";
import { Wallet, ShieldCheck, RefreshCw, Plus, CheckCircle2, AlertCircle, FileCheck2, LockKeyhole, CalendarDays } from "lucide-react";

const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0));
const dateText = value => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const statusClass = value => "status status-" + String(value || "unknown").toLowerCase().replaceAll(" ", "-");

export default function PayrollWorkspace({ api, claims, connected, onChanged }) {
  const [data, setData] = useState({ employees: [], periods: [], runs: [], ruleSets: [] });
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [compensation, setCompensation] = useState([]);
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [lines, setLines] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const apiRef = useRef(api);
  const changedRef = useRef(onChanged);
  apiRef.current = api;
  changedRef.current = onChanged;
  const permissions = Array.isArray(claims?.permissions) ? claims.permissions : [];
  const can = permission => permissions.includes(permission);
  const permissionKey = permissions.slice().sort().join("|");

  const load = useCallback(async () => {
    if (!connected) return;
    setLoading(true); setError("");
    const jobs = [];
    if (can("hr:employee:read")) jobs.push(["employees", "/api/v1/hr/employees"]);
    if (can("payroll:read")) {
      jobs.push(["periods", "/api/v1/payroll/periods"]);
      jobs.push(["runs", "/api/v1/payroll/runs"]);
    }
    if (can("payroll:rules:read")) jobs.push(["ruleSets", "/api/v1/payroll/rule-sets"]);
    const results = await Promise.all(jobs.map(async ([key, path]) => {
      try { return [key, await apiRef.current(path), ""]; }
      catch (e) { return [key, [], e.message]; }
    }));
    const next = { employees: [], periods: [], runs: [], ruleSets: [] };
    const failures = [];
    results.forEach(([key, value, message]) => { next[key] = Array.isArray(value) ? value : []; if (message) failures.push(key + ": " + message); });
    setData(next);
    if (failures.length) setError(failures.join(" · "));
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- 'can' derives from 'permissions'
  }, [connected, permissionKey]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (can("payroll:compensation:read") && selectedEmployeeId && connected) {
      apiRef.current("/api/v1/payroll/compensation?employee_id=" + encodeURIComponent(selectedEmployeeId))
        .then(setCompensation).catch(e => setError(e.message));
    } else setCompensation([]);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- 'can' derives from 'permissions'
  }, [selectedEmployeeId, connected, permissionKey]);

  useEffect(() => {
    if (selectedRunId && connected && can("payroll:read")) {
      Promise.all([
        apiRef.current("/api/v1/payroll/runs/" + selectedRunId + "/entries"),
        apiRef.current("/api/v1/payroll/runs/" + selectedRunId + "/summary"),
      ]).then(([rows, totals]) => { setEntries(rows); setSummary(totals); })
        .catch(e => setError(e.message));
    } else { setEntries([]); setSummary(null); }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- 'can' derives from 'permissions'
  }, [selectedRunId, connected, permissionKey]);

  const run = async (path, method, payload, message) => {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRef.current(path, { method, ...(payload === undefined ? {} : { body: JSON.stringify(payload) }) });
      setNotice(message); setForm({});
      await load();
      if (selectedRunId && can("payroll:read")) {
        const [rows, totals] = await Promise.all([
          apiRef.current("/api/v1/payroll/runs/" + selectedRunId + "/entries"),
          apiRef.current("/api/v1/payroll/runs/" + selectedRunId + "/summary"),
        ]);
        setEntries(rows); setSummary(totals);
      }
      if (selectedEmployeeId && can("payroll:compensation:read")) {
        setCompensation(await apiRef.current("/api/v1/payroll/compensation?employee_id=" + encodeURIComponent(selectedEmployeeId)));
      }
      if (changedRef.current) await changedRef.current();
    } catch (e) { setError(e.message || "The payroll action could not be completed."); }
    finally { setBusy(false); }
  };

  const field = (key, label, type = "text", required = true) => (
    <label className="payroll-field" key={key}>{label}
      <input type={type} required={required} step={type === "number" ? "0.01" : undefined} value={form[key] ?? ""} onChange={e => setForm(current => ({ ...current, [key]: e.target.value }))}/>
    </label>
  );
  const selectField = (key, label, options) => (
    <label className="payroll-field" key={key}>{label}
      <select required value={form[key] ?? ""} onChange={e => setForm(current => ({ ...current, [key]: e.target.value }))}><option value="">Select…</option>{options.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select>
    </label>
  );
  const submit = (e, path, payload, message) => { e.preventDefault(); run(path, "POST", payload, message); };

  if (!connected) return <section className="payroll-panel"><Empty title="Connect an authorized session" text="Payroll and compensation records are not available in preview mode."/></section>;

  return <div className="payroll-workspace">
    <div className="payroll-statusbar"><div><span className="status-dot online"/><b>Payroll API connected</b><small>Compensation and payroll permissions are evaluated separately</small></div><button className="btn btn-quiet" onClick={load} disabled={loading}><RefreshCw size={14}/>{loading ? "Refreshing…" : "Refresh"}</button></div>
    {notice && <div className="people-notice success"><CheckCircle2 size={16}/>{notice}</div>}
    {error && <div className="people-notice error"><AlertCircle size={16}/>{error}</div>}

    {can("payroll:compensation:read") && <section className="payroll-panel">
      <Heading icon={LockKeyhole} title="Restricted compensation records" subtitle="Visible only with payroll:compensation:read"/>
      {can("hr:employee:read") ? <label className="payroll-picker">Employee record<select value={selectedEmployeeId} onChange={e=>setSelectedEmployeeId(e.target.value)}><option value="">Select employee…</option>{data.employees.map(x=><option key={x.id} value={x.id}>{x.first_name} {x.last_name} · {x.employee_code || x.id}</option>)}</select></label> : <label className="payroll-picker">Employee ID<input value={selectedEmployeeId} onChange={e=>setSelectedEmployeeId(e.target.value)} placeholder="Enter authorized employee ID"/></label>}
      {compensation.map(item=><article className="payroll-record" key={item.id}><div><b>{item.currency} {money(item.gross_amount,item.currency)} · {item.frequency}</b><span className={statusClass(item.status)}>{item.status}</span></div><small>{item.pay_basis} · Effective {dateText(item.effective_from)} – {dateText(item.effective_to)}</small>
        {item.status==="Pending Approval" && can("payroll:compensation:approve") && <div className="payroll-actions"><button className="btn btn-quiet" disabled={busy||item.created_by===claims.sub} onClick={()=>run("/api/v1/payroll/compensation/"+item.id+"/decision","POST",{decision:"Approved",approval_note:"Independently reviewed"},"Compensation approved.")}>Approve</button><button className="btn btn-quiet" disabled={busy||item.created_by===claims.sub} onClick={()=>run("/api/v1/payroll/compensation/"+item.id+"/decision","POST",{decision:"Rejected",approval_note:"Returned after independent review"},"Compensation rejected.")}>Reject</button></div>}
      </article>)}
      {!compensation.length && selectedEmployeeId && <Empty title="No compensation records" text="No compensation records are registered for this employee."/>}
    </section>}

    {can("payroll:compensation:write") && <section className="payroll-panel">
      <Heading icon={Plus} title="Propose compensation" subtitle="Every proposal requires independent approval before becoming approved compensation"/>
      <form className="payroll-form" onSubmit={e=>submit(e,"/api/v1/payroll/compensation",{
        employee_id:form.comp_employee || selectedEmployeeId, currency:(form.currency||"INR").toUpperCase(),
        pay_basis:form.pay_basis||"Fixed", gross_amount:form.gross_amount, frequency:form.frequency||"Monthly",
        effective_from:form.comp_effective_from, effective_to:form.comp_effective_to||null
      },"Compensation proposal submitted for independent approval.")}>
        {can("hr:employee:read") ? <label className="payroll-field">Employee<select required value={form.comp_employee||selectedEmployeeId} onChange={e=>setForm(current=>({...current,comp_employee:e.target.value}))}><option value="">Select employee…</option>{data.employees.map(x=><option key={x.id} value={x.id}>{x.first_name} {x.last_name} · {x.employee_code||x.id}</option>)}</select></label> : field("comp_employee","Employee ID") }
        {field("currency","Currency (ISO 4217)")} {field("gross_amount","Gross amount","number")}
        {selectField("pay_basis","Pay basis",[{value:"Fixed",label:"Fixed"},{value:"Hourly",label:"Hourly"},{value:"Daily",label:"Daily"}])}
        {selectField("frequency","Frequency",[{value:"Monthly",label:"Monthly"},{value:"Weekly",label:"Weekly"},{value:"Biweekly",label:"Biweekly"},{value:"Annual",label:"Annual"}])}
        {field("comp_effective_from","Effective from","date")}{field("comp_effective_to","Effective to","date",false)}
        <button className="btn btn-primary" disabled={busy||!(form.comp_employee||selectedEmployeeId)}><Plus size={14}/>Submit proposal</button>
      </form>
    </section>}

    {can("payroll:rules:read") && <section className="payroll-panel">
      <Heading icon={ShieldCheck} title="Payroll rule sets" subtitle="Owner-entered rules; only an independently approved set covering the run period is ever applied. No rates are built in." count={data.ruleSets.length}/>
      {can("payroll:rules:write") && <form className="payroll-form" onSubmit={e=>{
        const lines=(form.rs_lines||"").split("\n").map(x=>x.trim()).filter(Boolean).map(row=>{const [line_type,code,basis,value,cap,borne_by]=row.split(",").map(x=>x.trim());
          return {line_type,code,basis,...(basis==="fixed"?{fixed_amount:value}:{rate:value}),cap_amount:cap||null,borne_by:borne_by||"employee"};});
        submit(e,"/api/v1/payroll/rule-sets",{code:form.rs_code,currency:(form.rs_currency||"").toUpperCase(),effective_from:form.rs_from,effective_to:form.rs_to||null,rounding_mode:form.rs_rounding,lines},"Rule set proposed for independent approval.");}}>
        {field("rs_code","Rule set code")}{field("rs_currency","Currency")}{field("rs_from","Effective from","date")}{field("rs_to","Effective to","date",false)}
        {selectField("rs_rounding","Rounding mode",["half_up","half_even","down","up","ceiling","floor"].map(x=>({value:x,label:x})))}
        <label className="payroll-field">Lines, one per row: type,code,basis,rate-or-amount,cap,borne_by
          <textarea required rows={4} value={form.rs_lines??""} placeholder="deduction,CODE1,gross,0.000000,," onChange={e=>setForm(current=>({...current,rs_lines:e.target.value}))}/></label>
        <button className="btn btn-primary" disabled={busy}>Propose rule set</button>
      </form>}
      <div className="payroll-card-grid">{data.ruleSets.map(item=><article className="payroll-record" key={item.id}><div><b>{item.code} · {item.currency}</b><span className={statusClass(item.status)}>{item.status}</span></div>
        <small>{dateText(item.effective_from)} – {dateText(item.effective_to)} · {item.rounding_mode} · {item.lines.length} lines</small>
        {item.status==="Pending Approval" && can("payroll:rules:approve") && <div className="payroll-actions"><button className="btn btn-quiet" disabled={busy||item.created_by===claims.sub} onClick={()=>run("/api/v1/payroll/rule-sets/"+item.id+"/decision","POST",{decision:"Approved",approval_note:"Independently reviewed"},"Rule set approved.")}>Approve</button><button className="btn btn-quiet" disabled={busy||item.created_by===claims.sub} onClick={()=>run("/api/v1/payroll/rule-sets/"+item.id+"/decision","POST",{decision:"Rejected",approval_note:"Not accepted"},"Rule set rejected.")}>Reject</button></div>}
      </article>)}</div>
    </section>}

    {can("payroll:read") && <section className="payroll-panel">
      <Heading icon={CalendarDays} title="Payroll periods" subtitle="Period dates and lifecycle are controlled by the API" count={data.periods.length}/>
      {can("payroll:period:write") && <form className="payroll-form" onSubmit={e=>submit(e,"/api/v1/payroll/periods",{period_code:form.period_code,start_date:form.period_start,end_date:form.period_end},"Payroll period created.")}>
        {field("period_code","Period code")}{field("period_start","Start date","date")}{field("period_end","End date","date")}
        <button className="btn btn-primary" disabled={busy}>Create period</button>
      </form>}
      <div className="payroll-card-grid">{data.periods.map(item=><article className="payroll-record" key={item.id}><div><b>{item.period_code}</b><span className={statusClass(item.status)}>{item.status}</span></div><small>{dateText(item.start_date)} – {dateText(item.end_date)}</small></article>)}</div>
    </section>}

    {can("payroll:read") && <section className="payroll-panel">
      <Heading icon={Wallet} title="Payroll runs" subtitle="Prepare, reconcile, submit and independently approve payroll runs" count={data.runs.length}/>
      {can("payroll:run:write") && <form className="payroll-form" onSubmit={e=>submit(e,"/api/v1/payroll/runs",{period_id:form.run_period,run_code:form.run_code,currency:(form.run_currency||"INR").toUpperCase()},"Payroll run created.")}>
        {selectField("run_period","Payroll period",data.periods.filter(x=>x.status==="Open").map(x=>({value:x.id,label:x.period_code})))}
        {field("run_code","Run code")}{field("run_currency","Currency","text")}
        <button className="btn btn-primary" disabled={busy}>Create payroll run</button>
      </form>}
      <div className="payroll-card-grid">{data.runs.map(item=><button type="button" className={"payroll-run-card "+(selectedRunId===item.id?"selected":"")} key={item.id} onClick={()=>setSelectedRunId(item.id)}><div><b>{item.run_code}</b><span className={statusClass(item.status)}>{item.status}</span></div><small>{item.currency} · {data.periods.find(x=>x.id===item.period_id)?.period_code || "Period"}</small></button>)}</div>
    </section>}

    {selectedRunId && can("payroll:read") && <section className="payroll-panel">
      <Heading icon={FileCheck2} title="Run review and reconciliation" subtitle="Totals are read from persisted payroll entries"/>
      {summary && <div className="payroll-summary"><div><small>Employees</small><b>{summary.entry_count}</b></div><div><small>Gross total</small><b>{money(summary.gross_total,summary.currency)}</b></div><div><small>Deductions</small><b>{money(summary.deduction_total,summary.currency)}</b></div><div><small>Net total</small><b>{money(summary.net_total,summary.currency)}</b></div><div><small>Arithmetic</small><b>{summary.entries_reconciled?"Reconciled":"Mismatch"}</b></div></div>}
      {can("payroll:entry:write") && <form className="payroll-form" onSubmit={e=>submit(e,"/api/v1/payroll/runs/"+selectedRunId+"/entries",{
        employee_id:form.entry_employee || "", currency:(form.entry_currency||"INR").toUpperCase(),
        gross_amount:form.entry_gross, deduction_total:form.entry_deductions, net_amount:form.entry_net,
        breakdown:{source:"User-supplied payroll input",note:form.entry_note||""}
      },"Payroll entry added; totals recalculated from persisted values.")}>
        <h3>Add payroll input (manual/source-supplied)</h3>
        {can("hr:employee:read") ? <label className="payroll-field">Employee<select required value={form.entry_employee||""} onChange={e=>setForm(current=>({...current,entry_employee:e.target.value}))}><option value="">Select employee…</option>{data.employees.map(x=><option key={x.id} value={x.id}>{x.first_name} {x.last_name} · {x.employee_code||x.id}</option>)}</select></label> : field("entry_employee","Employee ID")}
        {field("entry_currency","Currency")} {field("entry_gross","Gross amount","number")} {field("entry_deductions","Deduction total","number")} {field("entry_net","Net amount","number")} {field("entry_note","Input source / note","text",false)}
        <button className="btn btn-primary" disabled={busy}>Add entry</button>
      </form>}
      <div className="payroll-table-wrap" tabIndex={0} role="region" aria-label="Scrollable data table"><table className="payroll-table"><thead><tr><th>Employee reference</th><th>Gross</th><th>Deductions</th><th>Net</th><th>Status</th></tr></thead><tbody>{entries.map(item=><tr key={item.id}><td>{item.employee_id}</td><td>{money(item.gross_amount,item.currency)}</td><td>{money(item.deduction_total,item.currency)}</td><td><b>{money(item.net_amount,item.currency)}</b></td><td><span className={statusClass(item.status)}>{item.status}</span></td></tr>)}</tbody></table></div>
      {lines && <div className="payroll-table-wrap" tabIndex={0} role="region" aria-label="Calculated lines"><table className="payroll-table"><thead><tr><th>Line</th><th>Type</th><th>Borne by</th><th>Basis</th><th>Rate</th><th>Amount</th><th>Rounding</th><th>Rule set</th></tr></thead><tbody>{lines.map(l=><tr key={l.id}><td>{l.code}</td><td>{l.line_type}</td><td>{l.borne_by}</td><td>{l.basis_amount}</td><td>{l.rate ?? "fixed"}</td><td>{l.amount}</td><td>{l.rounding_mode}</td><td>{String(l.rule_set_id).slice(0,8)}</td></tr>)}</tbody></table>{!lines.length&&<Empty title="No calculated lines" text="Lines appear after a calculation from an approved rule set."/>}</div>}
      <div className="payroll-actions">
        {entries.slice(0,50).map(item=><button key={item.id} type="button" className="btn btn-quiet" onClick={()=>apiRef.current("/api/v1/payroll/runs/"+selectedRunId+"/entries/"+item.id+"/lines").then(setLines).catch(e=>setError(e.message))}>Lines: {String(item.employee_id).slice(0,8)}</button>)}
        {can("payroll:entry:write") && ["Draft","Changes Requested"].includes(summary?.status) && summary?.entry_count>0 && <button className="btn btn-quiet" disabled={busy} onClick={()=>run("/api/v1/payroll/runs/"+selectedRunId+"/calculate","POST",undefined,"Deductions calculated from the approved rule set.")}>Calculate from approved rules</button>}
        {can("payroll:run:submit") && ["Draft","Changes Requested"].includes(summary?.status) && <button className="btn btn-primary" disabled={busy||!summary?.entry_count||!summary?.entries_reconciled} onClick={()=>run("/api/v1/payroll/runs/"+selectedRunId+"/submit","POST",{review_note:"Submitted after arithmetic reconciliation"},"Payroll run submitted for independent review.")}>Submit for review</button>}
        {can("payroll:run:approve") && summary?.status==="In Review" && <><button className="btn btn-quiet" disabled={busy||data.runs.find(x=>x.id===selectedRunId)?.created_by===claims.sub} onClick={()=>run("/api/v1/payroll/runs/"+selectedRunId+"/decision","POST",{decision:"Approved",approval_note:"Independently reviewed"},"Payroll run approved.")}>Approve run</button><button className="btn btn-quiet" disabled={busy||data.runs.find(x=>x.id===selectedRunId)?.created_by===claims.sub} onClick={()=>run("/api/v1/payroll/runs/"+selectedRunId+"/decision","POST",{decision:"Rejected",approval_note:"Changes required after review"},"Payroll run returned for correction.")}>Return run</button></>}
        {can("payroll:run:close") && summary?.status==="Approved" && <button className="btn btn-primary" disabled={busy} onClick={()=>run("/api/v1/payroll/runs/"+selectedRunId+"/close","POST",undefined,"Approved payroll run closed.")}>Close payroll run</button>}
      </div>
      {summary?.status && <p className="payroll-footnote">Current run status: <b>{summary.status}</b>. Payment initiation and statutory filing are not performed here.</p>}
    </section>}

    <div className="payroll-boundary"><ShieldCheck size={15}/><span>Compensation is shown only with payroll:compensation:read. API authorization is authoritative. This workspace validates supplied arithmetic; calculation uses only an owner-entered, independently approved rule set and never initiates salary payments.</span></div>
  </div>;
}

function Heading({ icon: Icon, title, subtitle, count }) { return <div className="payroll-heading"><span><Icon size={18}/></span><div><h2>{title}</h2><p>{subtitle}</p></div>{count!==undefined&&<small>{count}</small>}</div>; }
function Empty({ title, text }) { return <div className="people-empty"><ShieldCheck size={22}/><b>{title}</b><span>{text}</span></div>; }
