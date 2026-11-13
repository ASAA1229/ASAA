import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronUp, ClipboardList, Plus, RefreshCw, Send, ShieldCheck, X } from "lucide-react";

const emptyLine = () => ({ description: "", quantity: "1", unit_of_measure: "each", estimated_unit_cost: "" });
const dateAfterWeek = () => {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return date.toISOString().slice(0, 10);
};
const money = (value, currency = "INR") => new Intl.NumberFormat("en-IN", {
  style: "currency", currency, maximumFractionDigits: 2
}).format(Number(value || 0));

export default function ProcurementWorkspace({ requests = [], suppliers = [], api, claims = {}, onChanged, showSuppliers = false }) {
  const permissions = Array.isArray(claims.permissions) ? claims.permissions : [];
  const canCreate = permissions.includes("procurement:request:write");
  const canSubmit = permissions.includes("procurement:request:submit");
  const canReview = permissions.includes("procurement:request:review");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [expanded, setExpanded] = useState("");
  const [reasons, setReasons] = useState({});
  const [query, setQuery] = useState("");
  const [form, setForm] = useState({
    title: "", purpose: "", needed_by: dateAfterWeek(), currency: "INR",
    cost_center: "", project_reference: "", lines: [emptyLine()]
  });

  const filtered = useMemo(() => requests.filter(row =>
    [row.title, row.purpose, row.status, row.requested_by, row.cost_center, row.project_reference]
      .filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase())
  ), [requests, query]);

  const setField = (key, value) => setForm(current => ({ ...current, [key]: value }));
  const setLine = (index, key, value) => setForm(current => ({
    ...current,
    lines: current.lines.map((line, i) => i === index ? { ...line, [key]: value } : line)
  }));
  const total = form.lines.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.estimated_unit_cost || 0), 0);

  const runAction = async (action, requestId, payload) => {
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/api/v1/ap/purchase-requests/${requestId}/${action}`, {
        method: "POST", body: JSON.stringify(payload)
      });
      setNotice(action === "submit" ? "Purchase request submitted for independent review." : "Review decision recorded.");
      setReasons(current => ({ ...current, [requestId]: "" }));
      await onChanged?.();
    } catch (err) {
      setError(typeof err.message === "string" ? err.message : "The action could not be completed.");
    } finally { setBusy(false); }
  };

  const create = async event => {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await api("/api/v1/ap/purchase-requests", {
        method: "POST",
        body: JSON.stringify({
          title: form.title, purpose: form.purpose, needed_by: form.needed_by,
          currency: form.currency.toUpperCase(), cost_center: form.cost_center || null,
          project_reference: form.project_reference || null,
          lines: form.lines.map(line => ({
            description: line.description, quantity: line.quantity,
            unit_of_measure: line.unit_of_measure, estimated_unit_cost: line.estimated_unit_cost
          }))
        })
      });
      setForm({ title: "", purpose: "", needed_by: dateAfterWeek(), currency: "INR", cost_center: "", project_reference: "", lines: [emptyLine()] });
      setCreating(false); setNotice("Purchase request saved as Draft."); await onChanged?.();
    } catch (err) {
      setError(typeof err.message === "string" ? err.message : "Purchase request could not be created.");
    } finally { setBusy(false); }
  };

  return <div className="procurement-workspace">
    <section className="panel list-panel">
      <div className="list-heading">
        <div><h2>Purchase requests</h2><p>Raise a requisition, submit it and track independent review decisions.</p></div>
        {canCreate && <button className="btn btn-primary" onClick={() => { setCreating(value => !value); setError(""); }}><Plus size={15}/>{creating ? "Close form" : "New request"}</button>}
      </div>
      <div className="procurement-summary">
        <div><small>Total requests</small><b>{requests.length}</b></div>
        <div><small>Draft / returned</small><b>{requests.filter(row => ["Draft", "Returned"].includes(row.status)).length}</b></div>
        <div><small>Awaiting review</small><b>{requests.filter(row => row.status === "Submitted").length}</b></div>
        <div><small>Approved</small><b>{requests.filter(row => row.status === "Approved").length}</b></div>
      </div>
      {error && <div className="notice procurement-notice">{error}</div>}
      {notice && <div className="procurement-success"><Check size={15}/>{notice}</div>}
      {creating && <form className="procurement-form" onSubmit={create}>
        <div className="procurement-form-heading"><div><h3>New purchase request</h3><p>Creation saves a Draft. Submission is a separate action.</p></div><button type="button" className="icon-btn" onClick={() => setCreating(false)} aria-label="Close form"><X size={17}/></button></div>
        <div className="procurement-fields">
          <label>Request title<input required minLength="3" maxLength="200" value={form.title} onChange={e => setField("title", e.target.value)} /></label>
          <label>Needed by<input required type="date" min={new Date().toISOString().slice(0, 10)} value={form.needed_by} onChange={e => setField("needed_by", e.target.value)} /></label>
          <label>Currency<input required maxLength="3" minLength="3" value={form.currency} onChange={e => setField("currency", e.target.value.toUpperCase())} /></label>
          <label>Cost centre (optional)<input maxLength="120" value={form.cost_center} onChange={e => setField("cost_center", e.target.value)} /></label>
          <label>Project reference (optional)<input maxLength="160" value={form.project_reference} onChange={e => setField("project_reference", e.target.value)} /></label>
          <label className="procurement-wide">Business purpose<textarea required minLength="5" maxLength="4000" rows="3" value={form.purpose} onChange={e => setField("purpose", e.target.value)} /></label>
        </div>
        <div className="procurement-lines-heading"><h4>Request lines</h4><button type="button" className="btn btn-quiet" onClick={() => setForm(current => ({ ...current, lines: [...current.lines, emptyLine()] }))}><Plus size={14}/>Add line</button></div>
        {form.lines.map((line, index) => <div className="procurement-line" key={index}>
          <label>Description<input required minLength="2" maxLength="500" value={line.description} onChange={e => setLine(index, "description", e.target.value)} /></label>
          <label>Quantity<input required type="number" min="0.001" step="0.001" value={line.quantity} onChange={e => setLine(index, "quantity", e.target.value)} /></label>
          <label>Unit<input required maxLength="40" value={line.unit_of_measure} onChange={e => setLine(index, "unit_of_measure", e.target.value)} /></label>
          <label>Unit cost<input required type="number" min="0" step="0.01" value={line.estimated_unit_cost} onChange={e => setLine(index, "estimated_unit_cost", e.target.value)} /></label>
          <button type="button" className="icon-btn" disabled={form.lines.length === 1} onClick={() => setForm(current => ({ ...current, lines: current.lines.filter((_, i) => i !== index) }))} aria-label="Remove request line"><X size={16}/></button>
        </div>)}
        <div className="procurement-total"><span>Estimated total</span><b>{money(total, form.currency || "INR")}</b></div>
        <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={() => setCreating(false)}>Cancel</button><button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save draft"}</button></div>
      </form>}
      <div className="list-tools"><div className="search-box"><ClipboardList size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search purchase requests…"/></div><span>{filtered.length} requests</span></div>
      <div className="procurement-request-list">
        {filtered.map(row => {
          const isExpanded = expanded === row.id;
          const own = row.requested_by === claims.sub;
          const reason = reasons[row.id] || "";
          return <article className="procurement-request" key={row.id}>
            <button className="procurement-request-main" onClick={() => setExpanded(isExpanded ? "" : row.id)} aria-expanded={isExpanded}>
              <span className="procurement-request-icon"><ClipboardList size={18}/></span>
              <span className="procurement-request-copy"><b>{row.title}</b><small>{row.lines?.length || 0} lines · Needed by {row.needed_by} · {row.requested_by}</small></span>
              <span className="procurement-request-total">{money(row.estimated_total, row.currency)}</span>
              <span className={`status status-${(row.status || "unknown").toLowerCase()}`}>{row.status}</span>
              {isExpanded ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
            </button>
            {isExpanded && <div className="procurement-request-detail">
              <p>{row.purpose}</p>
              <div className="procurement-meta"><span>Cost centre: <b>{row.cost_center || "—"}</b></span><span>Project: <b>{row.project_reference || "—"}</b></span><span>Version: <b>{row.version}</b></span></div>
              <div className="table-wrap"><table><thead><tr><th>Description</th><th>Quantity</th><th>Unit cost</th><th>Line total</th></tr></thead><tbody>{(row.lines || []).map(line => <tr key={line.id}><td>{line.description}</td><td>{line.quantity} {line.unit_of_measure}</td><td>{money(line.estimated_unit_cost, row.currency)}</td><td>{money(line.estimated_line_total, row.currency)}</td></tr>)}</tbody></table></div>
              {row.reviewed_by && <p className="procurement-review-note"><ShieldCheck size={14}/> Reviewed by {row.reviewed_by} · {row.review_reason || "No reason supplied"}</p>}
              {(canSubmit && own && ["Draft", "Returned"].includes(row.status)) && <div className="procurement-action">
                <label>Submission note<input value={reason} onChange={e => setReasons(current => ({ ...current, [row.id]: e.target.value }))} placeholder="Explain why this request is ready for review" /></label>
                <button className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => runAction("submit", row.id, { expected_version: row.version, reason: reason.trim() })}><Send size={14}/>Submit for review</button>
              </div>}
              {(canReview && !own && row.status === "Submitted") && <div className="procurement-action">
                <label>Review reason<input value={reason} onChange={e => setReasons(current => ({ ...current, [row.id]: e.target.value }))} placeholder="Record the reason for your decision" /></label>
                <div className="procurement-review-actions">
                  <button className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => runAction("review", row.id, { expected_version: row.version, decision: "approve", reason: reason.trim() })}>Approve</button>
                  <button className="btn btn-quiet" disabled={busy || reason.trim().length < 3} onClick={() => runAction("review", row.id, { expected_version: row.version, decision: "return", reason: reason.trim() })}>Return</button>
                  <button className="btn btn-danger" disabled={busy || reason.trim().length < 3} onClick={() => runAction("review", row.id, { expected_version: row.version, decision: "reject", reason: reason.trim() })}>Reject</button>
                </div>
              </div>}
            </div>}
          </article>;
        })}
        {!filtered.length && <div className="empty-state"><div><ClipboardList size={20}/></div>{requests.length ? "No purchase requests match this search." : "No purchase requests are visible to this account yet."}</div>}
      </div>
      {!canCreate && !canSubmit && !canReview && <p className="field-help procurement-permission-note">This account has read-only access to purchase requests. Actions are shown only when the API session contains the required permissions.</p>}
    </section>
    {showSuppliers && <section className="panel list-panel">
      <div className="list-heading"><div><h2>Supplier directory</h2><p>Supplier records already available through Accounts Payable.</p></div><span>{suppliers.length} suppliers</span></div>
      <div className="table-wrap"><table><thead><tr><th>Supplier</th><th>Code</th><th>Category</th><th>Email</th><th>Status</th></tr></thead><tbody>
        {suppliers.map(row => <tr key={row.id}><td><b>{row.legal_name}</b><small>{row.trading_name || row.id.slice(0, 8)}</small></td><td>{row.supplier_code || "—"}</td><td>{row.category || "—"}</td><td>{row.email || "—"}</td><td>{row.status || "—"}</td></tr>)}
      </tbody></table>{!suppliers.length && <div className="empty-state">No supplier records available to this account.</div>}</div>
    </section>}
  </div>;
}
