import { useMemo, useState } from "react";
import { Building2, Check, Edit3, Plus, Save, ShieldCheck, X } from "lucide-react";

const fields = [
  ["legal_name", "Legal name", "text", true],
  ["trading_name", "Trading name", "text", false],
  ["supplier_code", "Supplier code", "text", false],
  ["email", "Accounts email", "email", false],
  ["phone", "Phone", "tel", false],
  ["website", "Website", "url", false],
  ["category", "Category", "text", false],
  ["registration_reference", "Registration reference", "text", false]
];
const statuses = ["Draft", "Pending Verification", "Active", "On Hold", "Suspended", "Archived"];

export default function SupplierWorkspace({ suppliers = [], api, claims = {}, onChanged }) {
  const permissions = Array.isArray(claims.permissions) ? claims.permissions : [];
  const canWrite = permissions.includes("supplier:write");
  const canStatus = permissions.includes("supplier:status");
  const canVerify = permissions.includes("supplier:verify");
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const [nextStatus, setNextStatus] = useState("Pending Verification");
  const [form, setForm] = useState({});
  const selected = suppliers.find(row => row.id === selectedId) || null;
  const filtered = useMemo(() => suppliers.filter(row =>
    [row.legal_name, row.trading_name, row.supplier_code, row.email, row.category, row.status]
      .filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase())
  ), [suppliers, query]);

  const startCreate = () => {
    setSelectedId(""); setCreating(true); setEditing(true); setError(""); setNotice(""); setReason("");
    setForm(Object.fromEntries(fields.map(([key]) => [key, ""])));
  };
  const startEdit = () => {
    if (!selected) return;
    setCreating(false); setEditing(true); setError(""); setNotice("");
    setForm(Object.fromEntries(fields.map(([key]) => [key, selected[key] || ""])));
  };
  const closeEdit = () => { setEditing(false); setCreating(false); setError(""); };
  const setField = (key, value) => setForm(current => ({ ...current, [key]: value }));

  const save = async event => {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const payload = Object.fromEntries(fields.map(([key]) => [key, form[key]?.trim() || null]));
      if (!creating) payload.expected_version = selected.version;
      await api(creating ? "/api/v1/ap/suppliers" : `/api/v1/ap/suppliers/${selected.id}`, {
        method: creating ? "POST" : "PATCH", body: JSON.stringify(payload)
      });
      setNotice(creating ? "Supplier created as Draft." : "Supplier details updated. Identity changes may require reverification.");
      setEditing(false); setCreating(false); await onChanged?.();
    } catch (err) {
      setError(err.message || "Supplier could not be saved.");
    } finally { setBusy(false); }
  };

  const changeStatus = async event => {
    event.preventDefault();
    if (!selected || reason.trim().length < 3) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/api/v1/ap/suppliers/${selected.id}/status`, {
        method: "POST",
        body: JSON.stringify({ expected_version: selected.version, status: nextStatus, reason: reason.trim() })
      });
      setNotice(`Supplier status changed to ${nextStatus}.`); setReason(""); await onChanged?.();
    } catch (err) {
      setError(err.message || "Supplier status could not be changed. Check the configured transition policy.");
    } finally { setBusy(false); }
  };

  return <div className="supplier-workspace">
    <section className="panel list-panel">
      <div className="list-heading"><div><h2>Supplier management</h2><p>Maintain supplier records, detect duplicates and control verification status.</p></div>
        {canWrite && <button className="btn btn-primary" onClick={startCreate}><Plus size={15}/>Add supplier</button>}
      </div>
      <div className="supplier-summary">
        <div><small>Total suppliers</small><b>{suppliers.length}</b></div>
        <div><small>Draft</small><b>{suppliers.filter(row => row.status === "Draft").length}</b></div>
        <div><small>Pending verification</small><b>{suppliers.filter(row => row.status === "Pending Verification").length}</b></div>
        <div><small>Active</small><b>{suppliers.filter(row => row.status === "Active").length}</b></div>
      </div>
      {error && <div className="notice">{error}</div>}
      {notice && <div className="supplier-success"><Check size={15}/>{notice}</div>}
      <div className="list-tools"><div className="search-box"><Building2 size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search suppliers…"/></div><span>{filtered.length} suppliers</span></div>
      <div className="supplier-layout">
        <div className="supplier-list">
          {filtered.map(row => <button key={row.id} className={`supplier-row ${selectedId === row.id ? "selected" : ""}`} onClick={() => { setSelectedId(row.id); setEditing(false); setCreating(false); setError(""); setNotice(""); }}>
            <span className="supplier-avatar"><Building2 size={17}/></span><span className="supplier-row-copy"><b>{row.legal_name}</b><small>{row.supplier_code || row.category || "Supplier record"}</small></span>
            <span className={`status status-${(row.status || "unknown").toLowerCase().replaceAll(" ", "-")}`}>{row.status}</span>
          </button>)}
          {!filtered.length && <div className="empty-state">No suppliers match this search.</div>}
        </div>
        <div className="supplier-detail">
          {editing && (creating || selected) ? <form className="supplier-form" onSubmit={save}>
            <div className="supplier-detail-heading"><div><h3>{creating ? "New supplier" : "Edit supplier"}</h3><p>{creating ? "New suppliers begin in Draft." : `Record version ${selected.version}`}</p></div><button type="button" className="icon-btn" onClick={closeEdit} aria-label="Close editor"><X size={17}/></button></div>
            {fields.map(([key, label, type, required]) => <label key={key}>{label}<input type={type} required={required} value={form[key] || ""} onChange={e => setField(key, e.target.value)}/></label>)}
            <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={closeEdit}>Cancel</button><button className="btn btn-primary" disabled={busy}><Save size={14}/>{busy ? "Saving…" : "Save supplier"}</button></div>
          </form> : selected ? <>
            <div className="supplier-detail-heading"><div><span className="eyebrow">SUPPLIER RECORD</span><h3>{selected.legal_name}</h3><p>{selected.trading_name || selected.supplier_code || selected.id}</p></div>
              {canWrite && !["Archived", "Suspended"].includes(selected.status) && <button className="btn btn-quiet" onClick={startEdit}><Edit3 size={14}/>Edit</button>}
            </div>
            <div className="supplier-status-line"><span className={`status status-${(selected.status || "unknown").toLowerCase().replaceAll(" ", "-")}`}>{selected.status}</span><span>Version {selected.version}</span></div>
            <div className="supplier-details-grid">
              <div><small>Supplier code</small><b>{selected.supplier_code || "—"}</b></div>
              <div><small>Category</small><b>{selected.category || "—"}</b></div>
              <div><small>Email</small><b>{selected.email || "—"}</b></div>
              <div><small>Phone</small><b>{selected.phone || "—"}</b></div>
              <div><small>Website</small><b>{selected.website || "—"}</b></div>
              <div><small>Registration reference</small><b>{selected.registration_reference || "—"}</b></div>
              <div><small>Created</small><b>{selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "—"}</b></div>
              <div><small>Last updated by</small><b>{selected.updated_by || "—"}</b></div>
            </div>
            {canStatus && <form className="supplier-status-form" onSubmit={changeStatus}>
              <div><h4><ShieldCheck size={15}/>Verification & lifecycle</h4><p>Allowed transitions are enforced by the server&apos;s configured supplier policy.</p></div>
              <label>Next status<select value={nextStatus} onChange={e => setNextStatus(e.target.value)}>{statuses.filter(status => status !== selected.status && (status !== "Active" || canVerify)).map(status => <option key={status}>{status}</option>)}</select></label>
              <label>Reason<input required minLength="3" value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason for this status change"/></label>
              <button className="btn btn-primary" disabled={busy || reason.trim().length < 3}>Apply status change</button>
            </form>}
            {selected.notes && <div className="supplier-notes"><small>Internal notes</small><p>{selected.notes}</p></div>}
          </> : <div className="supplier-empty"><Building2 size={28}/><b>Select a supplier</b><span>Choose a record to view its details, edit it or manage its verification lifecycle.</span></div>}
        </div>
      </div>
      {!canWrite && !canStatus && <p className="field-help">Read-only supplier access. Edit and lifecycle actions require explicit API permissions.</p>}
    </section>
  </div>;
}
