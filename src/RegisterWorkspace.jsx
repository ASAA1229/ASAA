import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, FilePlus2, RefreshCw, ShieldCheck } from "lucide-react";

const STATUSES = ["Draft", "In Review", "Approved", "Retired"];
const today = () => new Date().toISOString().slice(0, 10);

function FieldInput({ field, value, onChange }) {
  const label = field.required ? field.label : `${field.label} (optional)`;
  if (field.kind === "enum") {
    return <label>{label}<select value={value ?? ""} required={field.required} onChange={e => onChange(e.target.value)}>
      <option value="">Select...</option>{field.choices.map(c => <option key={c}>{c}</option>)}</select></label>;
  }
  if (field.kind === "bool") {
    return <label className="admin-checkbox"><input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} />{field.label}</label>;
  }
  if (field.kind === "transitions") {
    return <label>{label}<textarea rows={5} required={field.required} value={value ?? ""} placeholder='[{"from":"Draft","to":"Review","action":"submit"}]' onChange={e => onChange(e.target.value)} /></label>;
  }
  const type = field.kind === "date" ? "date" : field.kind === "int" ? "number" : "text";
  const pattern = field.kind === "money" ? "[0-9]+(\\.[0-9]{1,2})?" : field.kind === "currency" ? "[A-Z]{3}" : undefined;
  return <label>{label}<input type={type} pattern={pattern} inputMode={field.kind === "money" ? "decimal" : undefined} required={field.required} value={value ?? ""} onChange={e => onChange(e.target.value)} /></label>;
}

function toPayloadData(spec, values) {
  const data = {};
  for (const f of spec.fields) {
    const v = values[f.name];
    if (v === undefined || v === "" || v === false && f.kind !== "bool") continue;
    if (f.kind === "int") data[f.name] = Number(v);
    else if (f.kind === "strlist") data[f.name] = String(v).split(",").map(x => x.trim()).filter(Boolean);
    else if (f.kind === "transitions") data[f.name] = typeof v === "string" ? JSON.parse(v) : v;
    else data[f.name] = v;
  }
  return data;
}

function fromRecordData(spec, data) {
  const values = {};
  for (const f of spec.fields) {
    const v = data?.[f.name];
    values[f.name] = f.kind === "strlist" && Array.isArray(v) ? v.join(", ") : f.kind === "transitions" && v ? JSON.stringify(v) : v;
  }
  return values;
}

export default function RegisterWorkspace({ name, types: typeKeys, api, claims = {}, connected, onChanged, renewals = false }) {
  const permissions = Array.isArray(claims.permissions) ? claims.permissions : [];
  const can = (type, action) => permissions.includes(`register:${type}:${action}`);
  const [catalogue, setCatalogue] = useState([]);
  const [active, setActive] = useState(typeKeys[0]);
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [form, setForm] = useState(null); // { mode: "create" | "edit", base, values }
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const readable = useMemo(() => typeKeys.filter(k => can(k, "read")), [typeKeys, permissions.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  const spec = catalogue.find(t => t.key === active);
  const selected = records.find(r => r.id === selectedId);

  const load = useCallback(async () => {
    if (!connected || !readable.includes(active)) return;
    setLoading(true); setError("");
    try {
      const qs = new URLSearchParams({ ...(statusFilter ? { status: statusFilter } : {}), ...(query ? { q: query } : {}) }).toString();
      const [list, sum, cat] = await Promise.all([
        api(`/api/v1/registers/${active}${qs ? `?${qs}` : ""}`), api(`/api/v1/registers/${active}/summary`),
        catalogue.length ? Promise.resolve(catalogue) : api("/api/v1/registers/types")]);
      setRecords(Array.isArray(list) ? list : []); setSummary(sum); setCatalogue(cat);
    } catch (e) { setError(e.message || "The register could not be loaded."); }
    finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, active, statusFilter, query, readable.join("|")]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!typeKeys.includes(active)) setActive(typeKeys[0]); }, [typeKeys, active]);

  const [due, setDue] = useState([]);
  useEffect(() => {
    if (!renewals || !connected || !readable.includes("contract")) return;
    api("/api/v1/registers/contract/renewals?within_days=90").then(rows => setDue(Array.isArray(rows) ? rows : [])).catch(e => setError(e.message || "Renewals could not be loaded."));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renewals, connected, records, readable.join("|")]);

  const run = async (path, method, body, message) => {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api(path, { method, body: JSON.stringify(body) });
      setNotice(message); setForm(null); setReason("");
      if (result?.id) setSelectedId(result.id);
      await load(); await onChanged?.();
    } catch (e) { setError(e.message || "The change could not be saved."); }
    finally { setBusy(false); }
  };

  const submitForm = event => {
    event.preventDefault();
    let data;
    try { data = toPayloadData(spec, form.values); } catch { setError("Transitions must be valid JSON."); return; }
    const base = form.base;
    if (form.mode === "create") {
      run(`/api/v1/registers/${active}`, "POST", { code: base.code, title: base.title, summary: base.summary || null, review_due: base.review_due || null, data }, `${spec.label} created as Draft.`);
    } else {
      run(`/api/v1/registers/${active}/${selected.id}`, "PATCH", { expected_version: selected.version, title: base.title, summary: base.summary || null, review_due: base.review_due || null, data }, "Draft updated.");
    }
  };

  if (!connected) return <section className="panel list-panel"><div className="admin-empty"><ShieldCheck /><b>Connect an authorized identity session</b><span>{name} data is not available in unauthenticated preview mode.</span></div></section>;
  if (!readable.length) return <section className="panel list-panel"><div className="admin-empty"><ShieldCheck /><b>Access not granted</b><span>This session does not include register:{typeKeys[0]}:read.</span></div></section>;

  const action = (kind, body, message) => run(`/api/v1/registers/${active}/${selected.id}/${kind}`, "POST", { expected_version: selected.version, ...body }, message);
  const baseField = (key, label, type = "text", required = false) => <label>{label}{required ? "" : " (optional)"}<input type={type} required={required} maxLength={key === "code" ? 60 : undefined}
    value={form.base[key] ?? ""} onChange={e => setForm(f => ({ ...f, base: { ...f.base, [key]: e.target.value } }))} /></label>;

  return <div className="admin-workspace"><section className="panel list-panel">
    <div className="list-heading"><div><h2>{name}</h2><p>{spec ? spec.plural : "Governed records"} are versioned, reviewed by a second person and audited. They record governance information; they do not enforce it.</p></div>
      <div className="workforce-buttons">
        <button className="btn btn-quiet" onClick={load} disabled={loading}><RefreshCw size={14} />Refresh</button>
        {spec && can(active, "write") && <button className="btn btn-primary" onClick={() => setForm({ mode: "create", base: {}, values: {} })}><FilePlus2 size={14} />New {spec.label.toLowerCase()}</button>}
      </div></div>
    {renewals && <section className="admin-records" aria-label="Upcoming renewals"><h3>Renewals due within 90 days (approved contracts)</h3>
      {!due.length ? <p className="field-help">No approved contract renews in the next 90 days.</p> : <ul>{due.map(r => <li key={r.id}><b>{r.code}</b> {r.title} - renews {r.renewal_date} ({r.days_until_renewal < 0 ? `${-r.days_until_renewal} days overdue` : `in ${r.days_until_renewal} days`})</li>)}</ul>}</section>}
    {typeKeys.length > 1 && <div className="module-tabbar" role="tablist" aria-label="Register type">{typeKeys.map(k => <button key={k} role="tab" aria-selected={active === k} className={active === k ? "selected" : ""} disabled={!can(k, "read")}
      onClick={() => { setActive(k); setSelectedId(""); setForm(null); setRecords([]); }}>{catalogue.find(t => t.key === k)?.plural || k}</button>)}</div>}
    {error && <div className="notice" role="alert">{error}</div>}
    {notice && <div className="admin-success" role="status"><Check size={15} />{notice}</div>}
    {summary && <div className="module-status-strip" aria-label="Status summary">{STATUSES.map(s => <span key={s}><b>{summary.by_status[s]}</b> {s}</span>)}<span><b>{summary.review_overdue}</b> review overdue</span></div>}
    <div className="list-tools"><label className="search-box">Search<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Code or title" /></label>
      <label>Status<select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="">All</option>{STATUSES.map(s => <option key={s}>{s}</option>)}</select></label></div>

    {form && spec && <form className="admin-form" onSubmit={submitForm} aria-label={form.mode === "create" ? `New ${spec.label}` : `Edit ${spec.label}`}>
      <h3>{form.mode === "create" ? `New ${spec.label.toLowerCase()}` : `Edit draft ${selected?.code}`}</h3>
      {form.mode === "create" && baseField("code", "Code", "text", true)}
      {baseField("title", "Title", "text", true)}{baseField("summary", "Summary")}{baseField("review_due", "Review due", "date")}
      {spec.fields.map(f => <FieldInput key={f.name} field={f} value={form.values[f.name]} onChange={v => setForm(cur => ({ ...cur, values: { ...cur.values, [f.name]: v } }))} />)}
      <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary" disabled={busy}>{busy ? "Saving..." : "Save draft"}</button></div>
    </form>}

    {loading && !records.length ? <div className="admin-empty" role="status">Loading records...</div> : !records.length
      ? <div className="admin-empty"><FilePlus2 /><b>No {spec ? spec.plural.toLowerCase() : "records"} found</b><span>{statusFilter || query ? "Adjust the filters." : "Create the first record when authorized."}</span></div>
      : <div className="people-table-wrap" tabIndex={0} role="region" aria-label="Register records"><table className="people-table"><thead><tr><th>Code</th><th>Title</th><th>Rev.</th><th>Status</th><th>Owner</th><th>Review due</th><th>Actions</th></tr></thead><tbody>
        {records.map(r => <tr key={r.id} className={r.id === selectedId ? "selected" : ""}><td><b>{r.code}</b></td><td>{r.title}</td><td>{r.revision}</td>
          <td><span className={`status status-${r.status.toLowerCase().replace(" ", "-")}`}>{r.status}</span></td><td>{r.owner_subject}</td><td>{r.review_due || "-"}</td>
          <td><button className="btn btn-quiet" aria-label={`Open ${r.code} revision ${r.revision}`} onClick={() => { setSelectedId(r.id); setForm(null); setReason(""); }}>Open</button></td></tr>)}
      </tbody></table></div>}

    {selected && spec && !form && <section className="admin-records" aria-label={`Record ${selected.code}`}>
      <h3>{selected.code} - {selected.title} (revision {selected.revision}, {selected.status})</h3>
      {selected.summary && <p>{selected.summary}</p>}
      <dl className="admin-detail-grid">{spec.fields.map(f => <div key={f.name}><dt>{f.label}</dt><dd>{selected.data?.[f.name] === undefined ? "-" : typeof selected.data[f.name] === "object" ? JSON.stringify(selected.data[f.name]) : String(selected.data[f.name])}</dd></div>)}
        <div><dt>Created by</dt><dd>{selected.created_by}</dd></div><div><dt>Reviewed by</dt><dd>{selected.reviewed_by || "-"}</dd></div>{selected.review_reason && <div><dt>Review note</dt><dd>{selected.review_reason}</dd></div>}</dl>
      <div className="admin-review-controls">
        {selected.status === "Draft" && can(active, "write") && <><button className="btn btn-quiet" onClick={() => setForm({ mode: "edit", base: { title: selected.title, summary: selected.summary || "", review_due: selected.review_due || "" }, values: fromRecordData(spec, selected.data) })}>Edit draft</button>
          <button className="btn btn-primary" disabled={busy} onClick={() => action("submit", {}, "Submitted for independent review.")}>Submit for review</button></>}
        {selected.status === "In Review" && can(active, "review") && <>
          <label>Review reason<input value={reason} onChange={e => setReason(e.target.value)} placeholder="At least 3 characters" /></label>
          <button className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => action("review", { decision: "Approve", reason: reason.trim() }, "Approved.")}>Approve</button>
          <button className="btn btn-quiet" disabled={busy || reason.trim().length < 3} onClick={() => action("review", { decision: "Reject", reason: reason.trim() }, "Returned to Draft.")}>Reject</button></>}
        {selected.status === "Approved" && <>
          {can(active, "write") && <button className="btn btn-quiet" disabled={busy} onClick={() => action("revise", {}, "New draft revision created.")}>Start new revision</button>}
          {can(active, "review") && <><label>Retirement reason<input value={reason} onChange={e => setReason(e.target.value)} placeholder="At least 3 characters" /></label>
            <button className="btn btn-quiet" disabled={busy || reason.trim().length < 3} onClick={() => action("retire", { reason: reason.trim() }, "Retired.")}>Retire</button></>}</>}
      </div>
      <small className="field-help">Effective from {selected.effective_from || "not set"}{selected.effective_to ? ` to ${selected.effective_to}` : ""}. Today is {today()}.</small>
    </section>}
  </section></div>;
}
