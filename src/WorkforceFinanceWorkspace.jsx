import { useMemo, useState } from "react";
import { Check, Clock3, Plus, Receipt, Send, ShieldCheck, X } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);
const weekLater = () => { const d = new Date(); d.setDate(d.getDate() + 7); return d.toISOString().slice(0, 10); };
const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0));
const blankEntry = () => ({ work_date: today(), project_reference: "", task_reference: "", description: "", hours: "8.00", billable: false });

export default function WorkforceFinanceWorkspace({ kind, records = [], api, claims = {}, onChanged }) {
  const isTime = kind === "timesheet";
  const permissions = Array.isArray(claims.permissions) ? claims.permissions : [];
  const canCreate = permissions.includes(isTime ? "tms:timesheet:write" : "expense:claim:write");
  const canSubmit = permissions.includes(isTime ? "tms:timesheet:submit" : "expense:claim:submit");
  const canReview = permissions.includes(isTime ? "tms:timesheet:review" : "expense:claim:review") && permissions.includes(isTime ? "tms:timesheet:read:all" : "expense:claim:read:all");
  const canReimburse = !isTime && permissions.includes("expense:claim:reimburse") && permissions.includes("expense:claim:read:all");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [reasons, setReasons] = useState({});
  const [references, setReferences] = useState({});
  const [form, setForm] = useState(isTime ? {
    period_start: today(), period_end: weekLater(), employee_reference: "", entries: [blankEntry()]
  } : {
    expense_date: today(), category_code: "", merchant: "", description: "", amount: "",
    currency: "INR", receipt_reference: "", project_reference: ""
  });

  const filtered = useMemo(() => records.filter(row =>
    (isTime
      ? [row.employee_reference, row.employee_subject, row.status, row.period_start, row.period_end]
      : [row.description, row.employee_subject, row.category_code, row.merchant, row.status, row.project_reference]
    ).filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase())
  ), [records, query, isTime]);

  const change = (key, value) => setForm(current => ({ ...current, [key]: value }));
  const changeEntry = (index, key, value) => setForm(current => ({ ...current, entries: current.entries.map((entry, i) => i === index ? { ...entry, [key]: value } : entry) }));
  const closeForm = () => { setCreating(false); setError(""); };

  const create = async event => {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload = isTime ? {
        ...form,
        entries: form.entries.map(entry => ({ ...entry, hours: entry.hours }))
      } : {
        ...form, amount: form.amount, currency: form.currency.toUpperCase(),
        merchant: form.merchant || null, receipt_reference: form.receipt_reference || null,
        project_reference: form.project_reference || null
      };
      await api(isTime ? "/api/v1/workforce-finance/timesheets" : "/api/v1/workforce-finance/expenses", {
        method: "POST", body: JSON.stringify(payload)
      });
      setCreating(false); setNotice(isTime ? "Timesheet saved as Draft." : "Expense claim saved as Draft."); await onChanged?.();
    } catch (err) { setError(err.message || "Record could not be created."); }
    finally { setBusy(false); }
  };

  const action = async (row, endpoint, payload, success) => {
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/api/v1/workforce-finance/${isTime ? "timesheets" : "expenses"}/${row.id}/${endpoint}`, {
        method: "POST", body: JSON.stringify(payload)
      });
      setNotice(success); setReasons(current => ({ ...current, [row.id]: "" })); setReferences(current => ({ ...current, [row.id]: "" }));
      await onChanged?.();
    } catch (err) { setError(err.message || "Workflow action could not be completed."); }
    finally { setBusy(false); }
  };

  const submitted = records.filter(row => row.status === "Submitted").length;
  const approved = records.filter(row => row.status === "Approved").length;

  return <div className="workforce-finance-workspace">
    <section className="panel list-panel">
      <div className="list-heading"><div><h2>{isTime ? "Timesheet management" : "Expense management"}</h2><p>{isTime ? "Capture dated work, submit periods and independently review hours." : "Capture claims, record independent decisions and track reimbursement references."}</p></div>
        {canCreate && <button className="btn btn-primary" onClick={() => { setCreating(value => !value); setError(""); }}><Plus size={15}/>{creating ? "Close form" : isTime ? "New timesheet" : "New claim"}</button>}
      </div>
      <div className="workforce-summary"><div><small>Total records</small><b>{records.length}</b></div><div><small>Draft / rejected</small><b>{records.filter(row => ["Draft", "Rejected"].includes(row.status)).length}</b></div><div><small>Submitted</small><b>{submitted}</b></div><div><small>{isTime ? "Approved" : "Approved / reimbursed"}</small><b>{isTime ? approved : records.filter(row => ["Approved", "Reimbursement Recorded"].includes(row.status)).length}</b></div></div>
      {error && <div className="notice">{error}</div>}{notice && <div className="workforce-success"><Check size={15}/>{notice}</div>}
      {creating && <form className="workforce-form" onSubmit={create}>
        <div className="workforce-form-head"><div><h3>{isTime ? "Create timesheet" : "Create expense claim"}</h3><p>New records are saved as Draft. Submission is a separate workflow step.</p></div><button type="button" className="icon-btn" aria-label="Close form" onClick={closeForm}><X size={16}/></button></div>
        {isTime ? <>
          <div className="workforce-fields">
            <label>Period start<input required type="date" value={form.period_start} onChange={e => change("period_start", e.target.value)}/></label>
            <label>Period end<input required type="date" min={form.period_start} value={form.period_end} onChange={e => change("period_end", e.target.value)}/></label>
            <label>Employee reference (optional)<input value={form.employee_reference} onChange={e => change("employee_reference", e.target.value)}/></label>
          </div>
          <div className="workforce-lines-head"><h4>Work entries</h4><button type="button" className="btn btn-quiet" onClick={() => setForm(current => ({ ...current, entries: [...current.entries, blankEntry()] }))}><Plus size={14}/>Add entry</button></div>
          {form.entries.map((entry, index) => <div className="workforce-entry" key={index}>
            <label>Date<input required type="date" min={form.period_start} max={form.period_end} value={entry.work_date} onChange={e => changeEntry(index, "work_date", e.target.value)}/></label>
            <label>Hours<input required type="number" min="0.01" max="24" step="0.01" value={entry.hours} onChange={e => changeEntry(index, "hours", e.target.value)}/></label>
            <label>Description<input required minLength="2" value={entry.description} onChange={e => changeEntry(index, "description", e.target.value)}/></label>
            <label>Project reference<input value={entry.project_reference} onChange={e => changeEntry(index, "project_reference", e.target.value)}/></label>
            <label>Task reference<input value={entry.task_reference} onChange={e => changeEntry(index, "task_reference", e.target.value)}/></label>
            <label className="workforce-check"><input type="checkbox" checked={entry.billable} onChange={e => changeEntry(index, "billable", e.target.checked)}/>Billable</label>
            <button type="button" className="icon-btn" disabled={form.entries.length === 1} onClick={() => setForm(current => ({ ...current, entries: current.entries.filter((_, i) => i !== index) }))} aria-label="Remove entry"><X size={15}/></button>
          </div>)}
        </> : <div className="workforce-fields">
          <label>Expense date<input required type="date" value={form.expense_date} onChange={e => change("expense_date", e.target.value)}/></label>
          <label>Category code<input required minLength="2" value={form.category_code} onChange={e => change("category_code", e.target.value)}/></label>
          <label>Description<input required minLength="2" value={form.description} onChange={e => change("description", e.target.value)}/></label>
          <label>Amount<input required type="number" min="0.01" step="0.01" value={form.amount} onChange={e => change("amount", e.target.value)}/></label>
          <label>Currency<input required minLength="3" maxLength="3" value={form.currency} onChange={e => change("currency", e.target.value.toUpperCase())}/></label>
          <label>Merchant (optional)<input value={form.merchant} onChange={e => change("merchant", e.target.value)}/></label>
          <label>Receipt reference (optional)<input value={form.receipt_reference} onChange={e => change("receipt_reference", e.target.value)}/></label>
          <label>Project reference (optional)<input value={form.project_reference} onChange={e => change("project_reference", e.target.value)}/></label>
        </div>}
        <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={closeForm}>Cancel</button><button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save draft"}</button></div>
      </form>}
      <div className="list-tools"><div className="search-box"><Clock3 size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder={isTime ? "Search timesheets…" : "Search expense claims…"}/></div><span>{filtered.length} records</span></div>
      <div className="workforce-records">{filtered.map(row => {
        const own = (isTime ? row.employee_subject : row.employee_subject) === claims.sub;
        const reason = reasons[row.id] || "";
        return <article className="workforce-record" key={row.id}>
          <div className="workforce-record-main">
            <span className="workforce-record-icon">{isTime ? <Clock3 size={18}/> : <Receipt size={18}/>}</span>
            <span className="workforce-record-copy"><b>{isTime ? row.employee_reference || row.employee_subject : row.description}</b><small>{isTime ? `${row.period_start} – ${row.period_end} · ${row.total_hours} hours` : `${row.category_code} · ${row.expense_date} · ${money(row.amount, row.currency)}`}</small><small>{isTime ? row.employee_subject : row.employee_subject}</small></span>
            <span className={`status status-${(row.status || "unknown").toLowerCase().replaceAll(" ", "-")}`}>{row.status}</span>
          </div>
          {row.review_reason && <p className="workforce-review-note"><ShieldCheck size={14}/>{row.review_reason}{row.reviewed_by ? ` · ${row.reviewed_by}` : ""}</p>}
          {(canSubmit && own && ["Draft", "Rejected"].includes(row.status)) && <div className="workforce-action">
            <label>Submission reason<input value={reason} onChange={e => setReasons(current => ({ ...current, [row.id]: e.target.value }))} placeholder="Explain why this record is ready for review"/></label>
            <button className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => action(row, "submit", { expected_version: row.version, reason: reason.trim() }, "Submitted for independent review.")}><Send size={14}/>Submit</button>
          </div>}
          {(canReview && !own && row.status === "Submitted") && <div className="workforce-action">
            <label>Review reason<input value={reason} onChange={e => setReasons(current => ({ ...current, [row.id]: e.target.value }))} placeholder="Reason for your review decision"/></label>
            <div className="workforce-buttons"><button className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => action(row, "review", { expected_version: row.version, decision: "approve", reason: reason.trim() }, "Approved successfully.")}>Approve</button><button className="btn btn-danger" disabled={busy || reason.trim().length < 3} onClick={() => action(row, "review", { expected_version: row.version, decision: "reject", reason: reason.trim() }, "Rejected with an audit reason.")}>Reject</button></div>
          </div>}
          {(!isTime && canReimburse && !own && row.status === "Approved") && <div className="workforce-action">
            <label>External reimbursement reference<input value={references[row.id] || ""} onChange={e => setReferences(current => ({ ...current, [row.id]: e.target.value }))} placeholder="Payment or reimbursement reference"/></label>
            <button className="btn btn-primary" disabled={busy || (references[row.id] || "").trim().length < 2} onClick={() => action(row, "reimburse", { expected_version: row.version, reimbursement_reference: references[row.id].trim() }, "Reimbursement reference recorded. No bank transfer was initiated.")}>Record reimbursement</button>
          </div>}
        </article>;
      })}{!filtered.length && <div className="empty-state">No records match this search.</div>}</div>
      {!canCreate && !canSubmit && !canReview && !canReimburse && <p className="field-help">Read-only access. Actions are displayed only when the session contains the required API permissions.</p>}
    </section>
  </div>;
}
