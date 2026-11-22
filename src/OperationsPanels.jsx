import { useCallback, useEffect, useState } from "react";
import { Check, RefreshCw } from "lucide-react";

const permissionsOf = claims => (Array.isArray(claims?.permissions) ? claims.permissions : []);
const today = () => new Date().toISOString().slice(0, 10);
const plusDays = days => { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); };
const cell = value => (value === null || value === undefined || value === "" ? "-" : String(value));

function useList(api, path, enabled) {
  const [state, setState] = useState({ rows: [], loading: false, error: "" });
  const load = useCallback(async () => {
    if (!enabled) return;
    setState(s => ({ ...s, loading: true, error: "" }));
    try {
      const data = await api(path);
      setState({ rows: Array.isArray(data) ? data : [], loading: false, error: "" });
    } catch (e) { setState(s => ({ ...s, loading: false, error: e.message || "Could not load data." })); }
  }, [api, path, enabled]);
  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}

function useActions() {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn, success, after) => {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); setNotice(success); await after?.(); }
    catch (e) { setError(e.message || "The action could not be completed."); }
    finally { setBusy(false); }
  };
  return { error, notice, busy, run };
}

function Messages({ error, notice }) {
  return <>{error && <div className="notice" role="alert">{error}</div>}{notice && <div className="admin-success" role="status"><Check size={15} />{notice}</div>}</>;
}

/* A list panel: columns are [header, accessor], actions are [label, permission, applies(row), handler(row)]. */
function RecordTable({ title, description, list, columns, actions = [], permissions, busy }) {
  return <section className="panel list-panel">
    <div className="list-heading"><div><h2>{title}</h2><p>{description}</p></div>
      <button className="btn btn-quiet" onClick={list.reload} disabled={list.loading}><RefreshCw size={14} />Refresh</button></div>
    {list.error && <div className="notice" role="alert">{list.error}</div>}
    {!list.rows.length && !list.loading ? <div className="admin-empty"><b>No records</b><span>Nothing to show for this session yet.</span></div>
      : <div className="table-wrap"><table><thead><tr>{columns.map(([h]) => <th key={h}>{h}</th>)}{actions.length > 0 && <th>Actions</th>}</tr></thead>
        <tbody>{list.rows.map(row => <tr key={row.id}>{columns.map(([h, get]) => <td key={h}>{cell(get(row))}</td>)}
          {actions.length > 0 && <td>{actions.filter(([, perm, applies]) => permissions.includes(perm) && applies(row)).map(([label, , , handler]) =>
            <button key={label} className="btn btn-quiet" disabled={busy} onClick={() => handler(row)}>{label}</button>)}</td>}</tr>)}</tbody></table></div>}
  </section>;
}

function Field({ label, children }) { return <label className="field"><span>{label}</span>{children}</label>; }

function ReasonField({ value, onChange, label = "Reason for the next decision" }) {
  return <Field label={label}><input value={value} onChange={e => onChange(e.target.value)} placeholder="Required for approvals, rejections and cancellations" /></Field>;
}

function AgingTable({ report }) {
  if (!report) return null;
  const buckets = ["current", "1-30", "31-60", "61-90", "90+", "total"];
  const currencies = Object.entries(report.by_currency || {});
  return <section className="panel list-panel"><div className="list-heading"><div><h2>Ageing as of {report.as_of}</h2><p>{report.note}</p></div></div>
    {!currencies.length ? <div className="admin-empty"><b>No open balances</b><span>Nothing is outstanding for this report.</span></div>
      : <div className="table-wrap"><table><thead><tr><th>Currency</th>{buckets.map(b => <th key={b}>{b}</th>)}<th>Invoices</th></tr></thead>
        <tbody>{currencies.map(([cur, row]) => <tr key={cur}><td>{cur}</td>{buckets.map(b => <td key={b}>{row[b]}</td>)}<td>{row.invoice_count}</td></tr>)}</tbody></table></div>}
    <small className="field-help">Sources: {(report.sources || []).join(", ")} - generated {new Date(report.generated_at).toLocaleString("en-IN")}</small>
  </section>;
}

/* ------------------------------------------------------------------ Payables: purchase orders, supplier invoices, payment batches */
export function PayablesPanel({ api, claims, connected }) {
  const permissions = permissionsOf(claims);
  const { error, notice, busy, run } = useActions();
  const [reason, setReason] = useState("");
  const [reference, setReference] = useState("");
  const [selected, setSelected] = useState([]);
  const [form, setForm] = useState({ supplier_id: "", purchase_order_id: "", invoice_number: "", currency: "INR", invoice_date: today(), due_date: plusDays(30), tax_total: "0.00", total: "" });
  const pos = useList(api, "/api/v1/ap/purchase-orders", connected && permissions.includes("ap:po:read"));
  const invoices = useList(api, "/api/v1/ap/supplier-invoices", connected && permissions.includes("ap:invoice:read"));
  const batches = useList(api, "/api/v1/ap/payment-batches", connected && permissions.includes("ap:payment:read"));
  const [aging, setAging] = useState(null);
  const canAging = connected && permissions.includes("ap:invoice:read");
  useEffect(() => { if (canAging) api("/api/v1/ap/aging").then(setAging).catch(() => setAging(null)); }, [api, canAging]);
  const reloadAll = async () => { await Promise.all([pos.reload(), invoices.reload(), batches.reload()]); if (canAging) setAging(await api("/api/v1/ap/aging").catch(() => null)); };
  const post = (path, body) => api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
  const decide = (base, decision) => row => run(() => { if (reason.trim().length < 3) throw new Error("Enter a reason first."); return post(`${base}/${row.id}/review`, { decision, reason: reason.trim() }); }, "Decision recorded.", reloadAll);
  const capture = event => {
    event.preventDefault();
    run(() => post("/api/v1/ap/supplier-invoices", { ...form, purchase_order_id: form.purchase_order_id || null, currency: form.currency.toUpperCase() }), "Supplier invoice captured. Run matching before review.", reloadAll);
  };
  const set = key => e => setForm(f => ({ ...f, [key]: e.target.value }));
  if (!connected) return null;
  const any = ["ap:po:read", "ap:invoice:read", "ap:payment:read"].some(p => permissions.includes(p));
  if (!any) return null;
  return <div className="admin-workspace">
    <Messages error={error} notice={notice} />
    <ReasonField value={reason} onChange={setReason} />
    {permissions.includes("ap:po:read") && <RecordTable title="Purchase orders" description="Maker-checker approval, then issue to the supplier. Goods are received against issued orders." list={pos} permissions={permissions} busy={busy}
      columns={[["Number", r => r.po_number], ["Supplier", r => r.supplier_id], ["Currency", r => r.currency], ["Total", r => r.total], ["Status", r => r.status]]}
      actions={[["Approve", "ap:po:review", r => r.status === "Draft", decide("/api/v1/ap/purchase-orders", "approve")], ["Reject", "ap:po:review", r => r.status === "Draft", decide("/api/v1/ap/purchase-orders", "reject")],
        ["Issue", "ap:po:issue", r => r.status === "Approved", r => run(() => post(`/api/v1/ap/purchase-orders/${r.id}/issue`), "Purchase order issued.", reloadAll)]]} />}
    {permissions.includes("ap:invoice:write") && <section className="panel list-panel"><div className="list-heading"><div><h2>Capture supplier invoice</h2><p>Record the supplier invoice. It is then matched against the purchase order and received goods.</p></div></div>
      <form className="form-grid" onSubmit={capture}>
        <Field label="Supplier id"><input required value={form.supplier_id} onChange={set("supplier_id")} /></Field>
        <Field label="Purchase order id (optional)"><input value={form.purchase_order_id} onChange={set("purchase_order_id")} /></Field>
        <Field label="Invoice number"><input required value={form.invoice_number} onChange={set("invoice_number")} /></Field>
        <Field label="Currency"><input required maxLength={3} value={form.currency} onChange={set("currency")} /></Field>
        <Field label="Invoice date"><input required type="date" value={form.invoice_date} onChange={set("invoice_date")} /></Field>
        <Field label="Due date"><input required type="date" value={form.due_date} onChange={set("due_date")} /></Field>
        <Field label="Tax total"><input required inputMode="decimal" value={form.tax_total} onChange={set("tax_total")} /></Field>
        <Field label="Invoice total"><input required inputMode="decimal" value={form.total} onChange={set("total")} /></Field>
        <button className="btn btn-primary" disabled={busy}>Capture invoice</button></form></section>}
    {permissions.includes("ap:invoice:read") && <RecordTable title="Supplier invoices" description="Captured, matched, reviewed by someone other than the capturer, then batched for payment." list={invoices} permissions={permissions} busy={busy}
      columns={[["Invoice", r => r.invoice_number], ["Supplier", r => r.supplier_id], ["Total", r => `${r.total} ${r.currency}`], ["Due", r => r.due_date], ["Status", r => r.status], ["Match", r => r.match_result?.exceptions?.join(", ") || r.match_result?.outcome]]}
      actions={[["Match", "ap:invoice:match", r => ["Captured", "Exception", "Matched"].includes(r.status), r => run(() => post(`/api/v1/ap/supplier-invoices/${r.id}/match`), "Matching complete.", reloadAll)],
        ["Approve", "ap:invoice:review", r => ["Matched", "Exception"].includes(r.status), decide("/api/v1/ap/supplier-invoices", "approve")], ["Reject", "ap:invoice:review", r => ["Matched", "Exception"].includes(r.status), decide("/api/v1/ap/supplier-invoices", "reject")],
        [selected.length ? "Toggle in batch" : "Select for batch", "ap:payment:write", r => r.status === "Approved", r => setSelected(s => (s.includes(r.id) ? s.filter(x => x !== r.id) : [...s, r.id]))]]} />}
    {permissions.includes("ap:payment:write") && selected.length > 0 && <div className="panel info-panel"><b>{selected.length} approved invoice(s) selected</b>
      <button className="btn btn-primary" disabled={busy} onClick={() => run(() => post("/api/v1/ap/payment-batches", { invoice_ids: selected }), "Payment batch created.", async () => { setSelected([]); await reloadAll(); })}>Create payment batch</button></div>}
    {permissions.includes("ap:payment:read") && <><Field label="Payment reference (required to record payment)"><input value={reference} onChange={e => setReference(e.target.value)} /></Field>
      <RecordTable title="Payment batches" description="Approved by someone other than the maker. Recording payment states that payment was made outside this system; no bank instruction is created." list={batches} permissions={permissions} busy={busy}
        columns={[["Batch", r => r.id.slice(0, 8)], ["Currency", r => r.currency], ["Total", r => r.total], ["Invoices", r => r.items.length], ["Status", r => r.status], ["Payment reference", r => r.payment_reference]]}
        actions={[["Approve", "ap:payment:approve", r => r.status === "Draft", r => run(() => post(`/api/v1/ap/payment-batches/${r.id}/approve`), "Payment batch approved.", reloadAll)],
          ["Record payment", "ap:payment:record", r => r.status === "Approved", r => run(() => { if (reference.trim().length < 3) throw new Error("Enter the payment reference first."); return post(`/api/v1/ap/payment-batches/${r.id}/record-payment`, { payment_reference: reference.trim() }); }, "Payment recorded.", reloadAll)],
          ["Cancel", "ap:payment:write", r => ["Draft", "Approved"].includes(r.status), r => run(() => { if (reason.trim().length < 3) throw new Error("Enter a reason first."); return post(`/api/v1/ap/payment-batches/${r.id}/cancel`, { reason: reason.trim() }); }, "Payment batch cancelled.", reloadAll)]]} /></>}
    <AgingTable report={aging} />
  </div>;
}

/* ------------------------------------------------------------------ Receivables: credit notes and ageing */
export function ReceivablesControlsPanel({ api, claims, connected }) {
  const permissions = permissionsOf(claims);
  const { error, notice, busy, run } = useActions();
  const [reason, setReason] = useState("");
  const [form, setForm] = useState({ invoice_id: "", amount: "", reason: "" });
  const canRead = connected && permissions.includes("ar:credit:read");
  const notes = useList(api, "/api/v1/ar/credit-notes", canRead);
  const [aging, setAging] = useState(null);
  const canAging = connected && permissions.includes("ar:invoice:read");
  useEffect(() => { if (canAging) api("/api/v1/ar/aging").then(setAging).catch(() => setAging(null)); }, [api, canAging]);
  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });
  const create = event => { event.preventDefault(); run(() => post("/api/v1/ar/credit-notes", form), "Credit note submitted for independent approval.", async () => { setForm({ invoice_id: "", amount: "", reason: "" }); await notes.reload(); }); };
  const decide = decision => row => run(() => { if (reason.trim().length < 3) throw new Error("Enter a reason first."); return post(`/api/v1/ar/credit-notes/${row.id}/review`, { decision, reason: reason.trim() }); }, "Decision recorded.", notes.reload);
  if (!connected || (!canRead && !canAging)) return null;
  return <div className="admin-workspace"><Messages error={error} notice={notice} />
    {canRead && <>
      {permissions.includes("ar:credit:write") && <section className="panel list-panel"><div className="list-heading"><div><h2>Credit note</h2><p>Reduces the outstanding balance of an issued invoice once approved by someone other than the maker.</p></div></div>
        <form className="form-grid" onSubmit={create}>
          <Field label="Invoice id"><input required value={form.invoice_id} onChange={e => setForm(f => ({ ...f, invoice_id: e.target.value }))} /></Field>
          <Field label="Amount"><input required inputMode="decimal" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} /></Field>
          <Field label="Reason"><input required minLength={3} value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} /></Field>
          <button className="btn btn-primary" disabled={busy}>Submit credit note</button></form></section>}
      <ReasonField value={reason} onChange={setReason} />
      <RecordTable title="Credit notes" description="Pending credit notes need an independent decision." list={notes} permissions={permissions} busy={busy}
        columns={[["Invoice", r => r.invoice_id], ["Amount", r => `${r.amount} ${r.currency}`], ["Reason", r => r.reason], ["Status", r => r.status], ["Maker", r => r.created_by]]}
        actions={[["Approve", "ar:credit:approve", r => r.status === "Pending Approval", decide("approve")], ["Reject", "ar:credit:approve", r => r.status === "Pending Approval", decide("reject")]]} /></>}
    <AgingTable report={aging} />
  </div>;
}

/* ------------------------------------------------------------------ Attendance */
export function AttendancePanel({ api, claims, connected }) {
  const permissions = permissionsOf(claims);
  const { error, notice, busy, run } = useActions();
  const [reason, setReason] = useState("");
  const [correction, setCorrection] = useState({ work_date: today(), clock_in: "09:00", clock_out: "17:00", reason: "" });
  const range = `date_from=${plusDays(-30)}&date_to=${today()}`;
  const canRecords = connected && permissions.includes("attendance:record:read");
  const records = useList(api, `/api/v1/attendance/records?${range}`, canRecords);
  const corrections = useList(api, "/api/v1/attendance/corrections", connected && permissions.includes("attendance:correction:read"));
  const shifts = useList(api, "/api/v1/attendance/shifts", connected && permissions.includes("attendance:shift:read"));
  const post = (path, body) => api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
  const reloadAll = async () => { await Promise.all([records.reload(), corrections.reload()]); };
  const decide = (base, decision) => row => run(() => { if (reason.trim().length < 3) throw new Error("Enter a reason first."); return post(`${base}/${row.id}/${base.endsWith("records") ? "overtime-review" : "review"}`, { decision, reason: reason.trim() }); }, "Decision recorded.", reloadAll);
  const requestCorrection = event => {
    event.preventDefault();
    const at = time => new Date(`${correction.work_date}T${time}:00`).toISOString();
    run(() => post("/api/v1/attendance/corrections", { work_date: correction.work_date, requested_clock_in: at(correction.clock_in), requested_clock_out: at(correction.clock_out), reason: correction.reason }), "Correction submitted for independent review.", reloadAll);
  };
  if (!connected) return null;
  if (!canRecords && !permissions.includes("attendance:clock") && !permissions.includes("attendance:shift:read")) return null;
  return <div className="admin-workspace"><Messages error={error} notice={notice} />
    {permissions.includes("attendance:clock") && <section className="panel list-panel"><div className="list-heading"><div><h2>Clock</h2><p>Records your own attendance. Your identity must be linked to an employee record.</p></div></div>
      <div className="form-actions"><button className="btn btn-primary" disabled={busy} onClick={() => run(() => post("/api/v1/attendance/clock-in"), "Clocked in.", reloadAll)}>Clock in</button>
        <button className="btn btn-quiet" disabled={busy} onClick={() => run(() => post("/api/v1/attendance/clock-out"), "Clocked out.", reloadAll)}>Clock out</button></div></section>}
    <ReasonField value={reason} onChange={setReason} />
    {canRecords && <RecordTable title="Attendance records (last 30 days)" description="Overtime is computed only when an owner-approved attendance policy exists." list={records} permissions={permissions} busy={busy}
      columns={[["Date", r => r.work_date], ["Employee", r => r.employee_id], ["In", r => r.clock_in], ["Out", r => r.clock_out], ["Worked (min)", r => r.worked_minutes], ["Overtime (min)", r => r.overtime_minutes], ["Overtime status", r => r.overtime_status]]}
      actions={[["Approve overtime", "attendance:overtime:review", r => r.overtime_status === "Pending", decide("/api/v1/attendance/records", "approve")], ["Reject overtime", "attendance:overtime:review", r => r.overtime_status === "Pending", decide("/api/v1/attendance/records", "reject")]]} />}
    {permissions.includes("attendance:correction:request") && <section className="panel list-panel"><div className="list-heading"><div><h2>Request a correction</h2><p>Missed or wrong clock times need an independent reviewer.</p></div></div>
      <form className="form-grid" onSubmit={requestCorrection}>
        <Field label="Work date"><input required type="date" value={correction.work_date} onChange={e => setCorrection(c => ({ ...c, work_date: e.target.value }))} /></Field>
        <Field label="Clock in"><input required type="time" value={correction.clock_in} onChange={e => setCorrection(c => ({ ...c, clock_in: e.target.value }))} /></Field>
        <Field label="Clock out"><input required type="time" value={correction.clock_out} onChange={e => setCorrection(c => ({ ...c, clock_out: e.target.value }))} /></Field>
        <Field label="Reason"><input required minLength={5} value={correction.reason} onChange={e => setCorrection(c => ({ ...c, reason: e.target.value }))} /></Field>
        <button className="btn btn-primary" disabled={busy}>Submit correction</button></form></section>}
    {permissions.includes("attendance:correction:read") && <RecordTable title="Corrections" description="Requests awaiting or past review." list={corrections} permissions={permissions} busy={busy}
      columns={[["Date", r => r.work_date], ["Employee", r => r.employee_id], ["Requested in", r => r.requested_clock_in], ["Requested out", r => r.requested_clock_out], ["Reason", r => r.reason], ["Status", r => r.status]]}
      actions={[["Approve", "attendance:correction:review", r => r.status === "Pending", decide("/api/v1/attendance/corrections", "approve")], ["Reject", "attendance:correction:review", r => r.status === "Pending", decide("/api/v1/attendance/corrections", "reject")]]} />}
    {permissions.includes("attendance:shift:read") && <RecordTable title="Shifts" description="Shift definitions used by the roster." list={shifts} permissions={permissions} busy={busy}
      columns={[["Code", r => r.code], ["Name", r => r.name], ["Start", r => r.start_time], ["End", r => r.end_time], ["Break (min)", r => r.break_minutes], ["Arrangement", r => r.work_arrangement], ["Status", r => r.status]]} />}
  </div>;
}

/* ------------------------------------------------------------------ Service delivery */
export function DeliveryPanel({ api, claims, connected, view = "engagements" }) {
  const permissions = permissionsOf(claims);
  const { error, notice, busy, run } = useActions();
  const [text, setText] = useState("");
  const [order, setOrder] = useState({ title: "", priority: "Normal" });
  const readPerm = { engagements: "delivery:engagement:read", services: "delivery:service:read", workorders: "delivery:workorder:read" }[view];
  const path = { engagements: "/api/v1/delivery/engagements", services: "/api/v1/delivery/services", workorders: "/api/v1/delivery/work-orders" }[view];
  const list = useList(api, path, connected && permissions.includes(readPerm));
  const [detail, setDetail] = useState(null);
  const post = (p, body) => api(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
  const needText = fn => row => run(() => { if (text.trim().length < 3) throw new Error("Enter the evidence, reason or reference first."); return fn(row); }, "Saved.", async () => { await list.reload(); if (detail) setDetail(await api(`/api/v1/delivery/engagements/${detail.id}`)); });
  const open = row => run(async () => setDetail(await api(`/api/v1/delivery/engagements/${row.id}`)), "Engagement loaded.");
  const createOrder = event => { event.preventDefault(); run(() => post("/api/v1/delivery/work-orders", order), "Work order created.", async () => { setOrder({ title: "", priority: "Normal" }); await list.reload(); }); };
  if (!connected || !permissions.includes(readPerm)) return null;
  return <div className="admin-workspace"><Messages error={error} notice={notice} />
    <Field label="Evidence, reason or client acceptance reference for the next action"><input value={text} onChange={e => setText(e.target.value)} /></Field>
    {view === "services" && <RecordTable title="Service catalogue" description="Services are approved by someone other than their maker before they can be used in engagements." list={list} permissions={permissions} busy={busy}
      columns={[["Code", r => r.code], ["Name", r => r.name], ["Tier", r => r.service_tier], ["Status", r => r.status]]}
      actions={[["Approve", "delivery:service:approve", r => r.status === "Draft", needText(r => post(`/api/v1/delivery/services/${r.id}/review`, { decision: "approve", reason: text.trim() }))],
        ["Reject", "delivery:service:approve", r => r.status === "Draft", needText(r => post(`/api/v1/delivery/services/${r.id}/review`, { decision: "reject", reason: text.trim() }))],
        ["Retire", "delivery:service:write", r => r.status === "Active", r => run(() => post(`/api/v1/delivery/services/${r.id}/retire`), "Service retired.", list.reload)]]} />}
    {view === "engagements" && <><RecordTable title="Client engagements" description="Statements of work with milestones, delivery evidence and independently recorded client acceptance." list={list} permissions={permissions} busy={busy}
      columns={[["Code", r => r.code], ["Title", r => r.title], ["SOW", r => r.sow_reference], ["Start", r => r.start_date], ["Status", r => r.status]]}
      actions={[["Open", "delivery:engagement:read", () => true, open],
        ["Activate", "delivery:engagement:manage", r => r.status === "Draft", needText(r => post(`/api/v1/delivery/engagements/${r.id}/status`, { status: "Active", reason: text.trim() }))],
        ["Complete", "delivery:engagement:manage", r => r.status === "Active", needText(r => post(`/api/v1/delivery/engagements/${r.id}/status`, { status: "Completed", reason: text.trim() }))],
        ["Cancel", "delivery:engagement:manage", r => ["Draft", "Active", "On Hold"].includes(r.status), needText(r => post(`/api/v1/delivery/engagements/${r.id}/status`, { status: "Cancelled", reason: text.trim() }))]]} />
      {detail && <section className="panel list-panel"><div className="list-heading"><div><h2>{detail.title}</h2><p>{detail.progress.accepted} of {detail.progress.milestones} milestones accepted - {detail.progress.overdue} overdue - billable accepted and not invoiced: {detail.progress.billable_accepted_not_invoiced}</p></div></div>
        <div className="table-wrap"><table><thead><tr><th>Milestone</th><th>Due</th><th>Billable</th><th>Status</th><th>Actions</th></tr></thead><tbody>{detail.milestones.map(m => <tr key={m.id}><td>{m.title}</td><td>{m.due_date}</td><td>{cell(m.billable_amount)}</td><td>{m.status}</td>
          <td>{permissions.includes("delivery:milestone:deliver") && ["Planned", "In Progress", "Rejected"].includes(m.status) && <button className="btn btn-quiet" disabled={busy} onClick={() => needText(r => post(`/api/v1/delivery/milestones/${r.id}/deliver`, { evidence: text.trim() }))(m)}>Mark delivered</button>}
            {permissions.includes("delivery:milestone:accept") && m.status === "Delivered" && <><button className="btn btn-quiet" disabled={busy} onClick={() => needText(r => post(`/api/v1/delivery/milestones/${r.id}/acceptance`, { decision: "accept", client_acceptance_reference: text.trim() }))(m)}>Record acceptance</button>
              <button className="btn btn-quiet" disabled={busy} onClick={() => needText(r => post(`/api/v1/delivery/milestones/${r.id}/acceptance`, { decision: "reject", client_acceptance_reference: text.trim() }))(m)}>Record rejection</button></>}</td></tr>)}</tbody></table></div></section>}</>}
    {view === "workorders" && <>{permissions.includes("delivery:workorder:write") && <section className="panel list-panel"><div className="list-heading"><div><h2>New work order</h2><p>Created Open, assigned to an active employee, executed, then verified by someone other than the person who completed it.</p></div></div>
      <form className="form-grid" onSubmit={createOrder}><Field label="Title"><input required minLength={3} value={order.title} onChange={e => setOrder(o => ({ ...o, title: e.target.value }))} /></Field>
        <Field label="Priority"><select value={order.priority} onChange={e => setOrder(o => ({ ...o, priority: e.target.value }))}>{["Low", "Normal", "High", "Urgent"].map(p => <option key={p}>{p}</option>)}</select></Field>
        <button className="btn btn-primary" disabled={busy}>Create work order</button></form></section>}
      <RecordTable title="Work orders" description="Queue of operational work orders." list={list} permissions={permissions} busy={busy}
        columns={[["Title", r => r.title], ["Priority", r => r.priority], ["Assignee", r => r.assignee_employee_id], ["Due", r => r.due_date], ["Status", r => r.status]]}
        actions={[["Start", "delivery:workorder:execute", r => r.status === "Assigned", r => run(() => post(`/api/v1/delivery/work-orders/${r.id}/start`), "Work started.", list.reload)],
          ["Complete", "delivery:workorder:execute", r => r.status === "In Progress", needText(r => post(`/api/v1/delivery/work-orders/${r.id}/complete`, { evidence: text.trim() }))],
          ["Verify", "delivery:workorder:verify", r => r.status === "Completed", needText(r => post(`/api/v1/delivery/work-orders/${r.id}/verify`, { decision: "approve", reason: text.trim() }))],
          ["Return", "delivery:workorder:verify", r => r.status === "Completed", needText(r => post(`/api/v1/delivery/work-orders/${r.id}/verify`, { decision: "reject", reason: text.trim() }))],
          ["Cancel", "delivery:workorder:write", r => !["Verified", "Cancelled"].includes(r.status), needText(r => post(`/api/v1/delivery/work-orders/${r.id}/cancel`, { evidence: text.trim() }))]]} /></>}
  </div>;
}
