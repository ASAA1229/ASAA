import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, RefreshCw, ShieldCheck } from "lucide-react";
import RegisterWorkspace from "./RegisterWorkspace.jsx";

const permissionsOf = claims => (Array.isArray(claims?.permissions) ? claims.permissions : []);
const stamp = value => (value ? new Date(value).toLocaleString("en-IN") : "-");

function Gate({ connected, allowed, name, permission, children }) {
  if (!connected) return <section className="panel list-panel"><div className="admin-empty"><ShieldCheck /><b>Connect an authorized identity session</b><span>{name} data is not available in unauthenticated preview mode.</span></div></section>;
  if (!allowed) return <section className="panel list-panel"><div className="admin-empty"><ShieldCheck /><b>Access not granted</b><span>This session does not include {permission}.</span></div></section>;
  return children;
}

function Messages({ error, notice }) {
  return <>{error && <div className="notice" role="alert">{error}</div>}{notice && <div className="admin-success" role="status"><Check size={15} />{notice}</div>}</>;
}

function useLoader(fn, deps) {
  const [state, setState] = useState({ data: null, loading: false, error: "" });
  const load = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: "" }));
    try { setState({ data: await fn(), loading: false, error: "" }); }
    catch (e) { setState(s => ({ ...s, loading: false, error: e.message || "Could not load data." })); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}

/* ------------------------------------------------------------------ Audit trail */
export function AuditTrailWorkspace({ api, claims, connected }) {
  const allowed = permissionsOf(claims).includes("audit:read");
  const [filters, setFilters] = useState({ action: "", actor_id: "", entity_type: "", outcome: "" });
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState("");
  const size = 25;
  const qs = useMemo(() => new URLSearchParams({ limit: String(size), offset: String(page * size), ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) }).toString(), [filters, page]);
  const { data, loading, error, reload } = useLoader(() => (connected && allowed ? api(`/api/v1/ap/audit-events?${qs}`) : Promise.resolve([])), [connected, allowed, qs]);
  const rows = Array.isArray(data) ? data : [];
  const set = key => e => { setFilters(f => ({ ...f, [key]: e.target.value })); setPage(0); };
  return <Gate connected={connected} allowed={allowed} name="Audit trail" permission="audit:read"><div className="admin-workspace"><section className="panel list-panel">
    <div className="list-heading"><div><h2>Audit trail</h2><p>Append-only application events for your organization: who did what, to which record, with what outcome. Read-only.</p></div>
      <button className="btn btn-quiet" onClick={reload} disabled={loading}><RefreshCw size={14} />Refresh</button></div>
    <Messages error={error} />
    <div className="list-tools"><label>Action starts with<input value={filters.action} onChange={set("action")} placeholder="supplier." /></label>
      <label>Actor<input value={filters.actor_id} onChange={set("actor_id")} /></label><label>Entity type<input value={filters.entity_type} onChange={set("entity_type")} placeholder="register:policy" /></label>
      <label>Outcome<select value={filters.outcome} onChange={set("outcome")}><option value="">Any</option><option>success</option><option>failure</option></select></label></div>
    {loading && !rows.length ? <div className="admin-empty" role="status">Loading audit events...</div> : !rows.length ? <div className="admin-empty"><b>No audit events match</b><span>Adjust the filters.</span></div>
      : <div className="people-table-wrap" tabIndex={0} role="region" aria-label="Audit events"><table className="people-table"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Outcome</th><th>Details</th></tr></thead><tbody>
        {rows.map(r => <><tr key={r.id}><td>{stamp(r.created_at)}</td><td>{r.actor_id}</td><td>{r.action}</td><td>{r.entity_type}</td><td>{r.outcome}</td>
          <td><button className="btn btn-quiet" aria-expanded={open === r.id} aria-label={`Details for ${r.action} ${r.id}`} onClick={() => setOpen(open === r.id ? "" : r.id)}>{open === r.id ? "Hide" : "Show"}</button></td></tr>
          {open === r.id && <tr key={r.id + "-d"}><td colSpan={6}><pre className="field-help">{JSON.stringify({ entity_id: r.entity_id, correlation_id: r.correlation_id, details: r.details }, null, 2)}</pre></td></tr>}</>)}
      </tbody></table></div>}
    <div className="modal-actions"><button className="btn btn-quiet" disabled={page === 0 || loading} onClick={() => setPage(p => p - 1)}>Previous</button>
      <span>Page {page + 1}</span><button className="btn btn-quiet" disabled={rows.length < size || loading} onClick={() => setPage(p => p + 1)}>Next</button></div>
  </section></div></Gate>;
}

/* ------------------------------------------------------------------ Notifications */
export function NotificationsWorkspace({ api, claims, connected }) {
  const perms = permissionsOf(claims);
  const can = p => perms.includes(p);
  const [tab, setTab] = useState("Outbox");
  const [statusFilter, setStatusFilter] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [form, setForm] = useState(null);
  const outbox = useLoader(() => (connected && can("notification:outbox:read")
    ? Promise.all([api(`/api/v1/notifications/messages${statusFilter ? `?status=${statusFilter}` : ""}`), api("/api/v1/notifications/status")]) : Promise.resolve(null)), [connected, statusFilter, tab]);
  const templates = useLoader(() => (connected && can("notification:template:read") ? api("/api/v1/notifications/templates") : Promise.resolve([])), [connected, tab]);
  const prefs = useLoader(() => (connected ? api("/api/v1/notifications/preferences/me") : Promise.resolve({})), [connected, tab]);
  const run = async (fn, message) => { setActionError(""); setNotice(""); try { await fn(); setNotice(message); setForm(null); outbox.reload(); templates.reload(); prefs.reload(); } catch (e) { setActionError(e.message || "The change could not be saved."); } };
  const [messages, status] = outbox.data || [[], null];
  return <Gate connected={connected} allowed name="Notifications & reminders" permission="notification:outbox:read"><div className="admin-workspace"><section className="panel list-panel">
    <div className="list-heading"><div><h2>Notifications &amp; reminders</h2><p>Templates, delivery status, retries and dead letters. Messages never contain salary, bank, tax or contact details.</p></div></div>
    <div className="module-tabbar" role="tablist" aria-label="Notification views">{["Outbox", "Templates", "My preferences"].map(t => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "selected" : ""} onClick={() => setTab(t)}>{t}</button>)}</div>
    <Messages error={actionError || outbox.error || templates.error || prefs.error} notice={notice} />
    {tab === "Outbox" && (!can("notification:outbox:read") ? <div className="admin-empty"><b>Access not granted</b><span>This session does not include notification:outbox:read.</span></div> : <>
      {status && <div className="module-status-strip" aria-label="Delivery summary"><span><b>{status.pending}</b> pending</span><span><b>{status.sent}</b> sent</span><span><b>{status.suppressed}</b> suppressed</span><span><b>{status.dead_letter}</b> dead letter</span>{status.alert && <span role="status"><b>Attention needed</b></span>}</div>}
      <div className="list-tools"><label>Status<select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="">All</option>{["Pending", "Sent", "DeadLetter", "Suppressed"].map(s => <option key={s}>{s}</option>)}</select></label>
        {can("notification:process") && <button className="btn btn-quiet" onClick={() => run(() => api("/api/v1/notifications/process", { method: "POST" }), "Delivery run completed.")}>Process due messages</button>}</div>
      {outbox.loading && !messages.length ? <div className="admin-empty" role="status">Loading messages...</div> : !messages.length ? <div className="admin-empty"><b>No messages</b><span>Messages appear when domain events use a template.</span></div>
        : <div className="people-table-wrap" tabIndex={0} role="region" aria-label="Notification messages"><table className="people-table"><thead><tr><th>Created</th><th>To</th><th>Template</th><th>Status</th><th>Attempts</th><th>Last error</th><th>Actions</th></tr></thead><tbody>
          {messages.map(m => <tr key={m.id}><td>{stamp(m.created_at)}</td><td>{m.recipient_subject}</td><td>{m.template_code}</td><td>{m.status}</td><td>{m.attempts}/{m.max_attempts}</td><td>{m.last_error || "-"}</td>
            <td>{m.status === "DeadLetter" && can("notification:process") && <button className="btn btn-quiet" aria-label={`Retry message ${m.id}`} onClick={() => run(() => api(`/api/v1/notifications/messages/${m.id}/retry`, { method: "POST" }), "Message queued for retry.")}>Retry</button>}</td></tr>)}</tbody></table></div>}</>)}
    {tab === "Templates" && (!can("notification:template:read") ? <div className="admin-empty"><b>Access not granted</b><span>This session does not include notification:template:read.</span></div> : <>
      {can("notification:template:write") && <div className="list-tools"><button className="btn btn-primary" onClick={() => setForm({ code: "", channel: "email", subject_template: "", body_template: "", variables: "" })}>New template</button></div>}
      {form && <form className="admin-form" aria-label="New notification template" onSubmit={e => { e.preventDefault(); run(() => api("/api/v1/notifications/templates", { method: "POST", body: JSON.stringify({ code: form.code, channel: form.channel, subject_template: form.subject_template, body_template: form.body_template, allowed_variables: form.variables.split(",").map(v => v.trim()).filter(Boolean) }) }), "Template created."); }}>
        <label>Code<input required value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} /></label>
        <label>Channel<select value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}>{["email", "sms", "chat", "in_app"].map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Subject template<input required value={form.subject_template} onChange={e => setForm({ ...form, subject_template: e.target.value })} placeholder="Action needed: {{item}}" /></label>
        <label>Body template<textarea required rows={3} value={form.body_template} onChange={e => setForm({ ...form, body_template: e.target.value })} /></label>
        <label>Allowed variables (comma separated)<input value={form.variables} onChange={e => setForm({ ...form, variables: e.target.value })} placeholder="item" /></label>
        <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary">Save template</button></div></form>}
      {!(templates.data || []).length ? <div className="admin-empty"><b>No templates</b><span>Create a template to enable a notification.</span></div>
        : <div className="people-table-wrap" tabIndex={0} role="region" aria-label="Notification templates"><table className="people-table"><thead><tr><th>Code</th><th>Channel</th><th>Subject</th><th>Variables</th><th>Active</th></tr></thead><tbody>
          {templates.data.map(t => <tr key={t.id}><td>{t.code}</td><td>{t.channel}</td><td>{t.subject_template}</td><td>{t.allowed_variables.join(", ") || "-"}</td><td>{t.active ? "Yes" : "No"}</td></tr>)}</tbody></table></div>}</>)}
    {tab === "My preferences" && <div className="admin-form" role="group" aria-label="My notification preferences"><h3>Channels I want to receive</h3>
      {Object.entries(prefs.data || {}).map(([channel, enabled]) => <label key={channel} className="admin-checkbox"><input type="checkbox" checked={!!enabled}
        onChange={e => run(() => api("/api/v1/notifications/preferences/me", { method: "PUT", body: JSON.stringify({ channel, enabled: e.target.checked }) }), `Preference for ${channel} saved.`)} />{channel}</label>)}</div>}
  </section></div></Gate>;
}

/* ------------------------------------------------------------------ Governance (authority register) */
const isoFromLocal = value => (value ? new Date(value).toISOString() : null);

export function GovernanceWorkspace({ api, claims, connected }) {
  const perms = permissionsOf(claims);
  const can = p => perms.includes(p);
  const [tab, setTab] = useState("Delegations");
  const [form, setForm] = useState(null);
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const delegations = useLoader(() => (connected && can("governance:delegation:read") ? api("/api/v1/governance/delegations") : Promise.resolve([])), [connected, tab]);
  const decisions = useLoader(() => (connected && can("governance:decision:read") ? api("/api/v1/governance/decisions") : Promise.resolve([])), [connected, tab]);
  const run = async (path, body, message) => { setActionError(""); setNotice(""); try { await api(path, { method: "POST", body: JSON.stringify(body) }); setNotice(message); setForm(null); setReason(""); delegations.reload(); decisions.reload(); } catch (e) { setActionError(e.message || "The change could not be saved."); } };
  const readAllowed = can("governance:delegation:read") || can("governance:decision:read");
  const rows = tab === "Delegations" ? delegations.data || [] : decisions.data || [];
  const base = tab === "Delegations" ? "/api/v1/governance/delegations" : "/api/v1/governance/decisions";
  const prefix = tab === "Delegations" ? "governance:delegation" : "governance:decision";
  return <Gate connected={connected} allowed={readAllowed} name="Governance" permission="governance:delegation:read or governance:decision:read"><div className="admin-workspace"><section className="panel list-panel">
    <div className="list-heading"><div><h2>Governance</h2><p>Authority delegations and the decision register. A registered delegation does not change anyone&apos;s permissions; independent approval is required.</p></div></div>
    <div className="module-tabbar" role="tablist" aria-label="Governance registers">{["Delegations", "Decisions"].map(t => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "selected" : ""} onClick={() => { setTab(t); setForm(null); }}>{t}</button>)}</div>
    <Messages error={actionError || delegations.error || decisions.error} notice={notice} />
    {can(`${prefix}:create`) && <div className="list-tools"><button className="btn btn-primary" onClick={() => setForm(tab === "Delegations" ? { delegator_subject: "", delegate_subject: "", scope_code: "", action_code: "", effective_from: "", effective_to: "", reason: "" } : { decision_type: "", title: "", scope_reference: "", rationale: "", decision_maker_subject: "" })}>New {tab === "Delegations" ? "delegation" : "decision"}</button></div>}
    {form && <form className="admin-form" aria-label={`New ${tab === "Delegations" ? "delegation" : "decision"}`} onSubmit={e => { e.preventDefault(); const body = tab === "Delegations" ? { ...form, effective_from: isoFromLocal(form.effective_from), effective_to: isoFromLocal(form.effective_to) } : form; run(base, body, "Created for independent review."); }}>
      {Object.keys(form).map(k => <label key={k}>{k.replaceAll("_", " ")}<input required type={k.startsWith("effective") ? "datetime-local" : "text"} value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} /></label>)}
      <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={() => setForm(null)}>Cancel</button><button className="btn btn-primary">Save</button></div></form>}
    {(tab === "Delegations" ? delegations : decisions).loading && !rows.length ? <div className="admin-empty" role="status">Loading...</div> : !rows.length ? <div className="admin-empty"><b>No {tab.toLowerCase()} registered</b><span>Records appear here once created.</span></div>
      : <div className="people-table-wrap" tabIndex={0} role="region" aria-label={`${tab} register`}><table className="people-table"><thead><tr>{tab === "Delegations" ? <><th>Delegator</th><th>Delegate</th><th>Scope</th><th>Action</th><th>Window</th></> : <><th>Title</th><th>Type</th><th>Decision maker</th><th>Scope</th></>}<th>Status</th><th>Actions</th></tr></thead><tbody>
        {rows.map(r => <tr key={r.id}>{tab === "Delegations" ? <><td>{r.delegator_subject}</td><td>{r.delegate_subject}</td><td>{r.scope_code}</td><td>{r.action_code}</td><td>{stamp(r.effective_from)} - {stamp(r.effective_to)}</td></> : <><td>{r.title}</td><td>{r.decision_type}</td><td>{r.decision_maker_subject}</td><td>{r.scope_reference}</td></>}
          <td>{r.status}{r.effective_now ? " (in force)" : ""}</td>
          <td>{r.status === "Pending Approval" && <>
            {can(`${prefix}:approve`) && <button className="btn btn-quiet" aria-label={`Approve ${r.id}`} onClick={() => run(`${base}/${r.id}/approve`, { expected_version: r.version, ...(reason.trim().length >= 3 ? { reason: reason.trim() } : {}) }, "Approved.")}>Approve</button>}
            {can(`${prefix}:reject`) && <button className="btn btn-quiet" aria-label={`Reject ${r.id}`} disabled={reason.trim().length < 3} onClick={() => run(`${base}/${r.id}/reject`, { expected_version: r.version, reason: reason.trim() }, "Rejected.")}>Reject</button>}</>}
            {tab === "Delegations" && r.status === "Approved" && can("governance:delegation:revoke") && <button className="btn btn-quiet" aria-label={`Revoke ${r.id}`} disabled={reason.trim().length < 3} onClick={() => run(`${base}/${r.id}/revoke`, { expected_version: r.version, reason: reason.trim() }, "Revoked.")}>Revoke</button>}</td></tr>)}</tbody></table></div>}
    {rows.length > 0 && <label className="admin-review-controls">Reason for rejection or revocation<input value={reason} onChange={e => setReason(e.target.value)} placeholder="At least 3 characters" /></label>}
  </section></div></Gate>;
}

/* ------------------------------------------------------------------ Reports (read-only aggregates) */
export function ReportsWorkspace({ api, connected, name = "Reports & dashboards", only }) {
  const { data, loading, error, reload } = useLoader(() => (connected ? api("/api/v1/reports/summary") : Promise.resolve(null)), [connected]);
  const sections = Object.entries(data?.sections || {}).filter(([key]) => !only || only.includes(key));
  const label = key => key.replaceAll("_", " ");
  return <Gate connected={connected} allowed name={name} permission="read access to the source records"><div className="admin-workspace"><section className="panel list-panel">
    <div className="list-heading"><div><h2>{name}</h2><p>Read-only aggregates computed from existing records you are allowed to read. Amounts are per currency and are never converted.</p></div>
      <button className="btn btn-quiet" onClick={reload} disabled={loading}><RefreshCw size={14} />Refresh</button></div>
    <Messages error={error} />
    {data && <small className="field-help">Generated {stamp(data.generated_at)}. {data.currency_note}</small>}
    {loading && !data ? <div className="admin-empty" role="status">Loading report...</div> : !sections.length ? <div className="admin-empty"><b>No report sections available</b><span>This session has no read permission for the underlying records.</span></div>
      : <div className="settings-grid">{sections.map(([key, section]) => <section className="panel info-panel" key={key} aria-label={section.label}><div className="panel-heading"><div><h2>{section.label}</h2><p>Source: {section.sources.join(", ")}</p></div></div>
        {Object.entries(section.data).map(([metric, value]) => Array.isArray(value) ? <div className="data-line" key={metric}><span>{label(metric)}</span><b>{value.length ? <ul>{value.map((item, i) => <li key={i}>{Object.values(item).join(" - ")}</li>)}</ul> : "none"}</b></div>
          : <div className="data-line" key={metric}><span>{label(metric)}</span><b>{typeof value === "object" ? (Object.keys(value).length ? Object.entries(value).map(([k, v]) => `${k}: ${typeof v === "object" ? Object.entries(v).map(([a, b]) => `${a} ${b}`).join(", ") : v}`).join(" · ") : "none") : String(value)}</b></div>)}</section>)}</div>}
  </section></div></Gate>;
}

/* ------------------------------------------------------------------ Backup & recovery */
export function BackupRecoveryWorkspace({ api, claims, connected }) {
  const allowed = permissionsOf(claims).includes("ops:backup:read");
  const { data, loading, error, reload } = useLoader(() => (connected && allowed ? api("/api/v1/operations/backup-status") : Promise.resolve(null)), [connected, allowed]);
  return <><div className="admin-workspace"><section className="panel list-panel">
    <div className="list-heading"><div><h2>Backup &amp; recovery</h2><p>Freshness of the scheduled encrypted backup and the recovery plans. RPO and RTO values are pending owner approval; a backup counts only once a restore has been demonstrated.</p></div>
      <button className="btn btn-quiet" onClick={reload} disabled={loading || !allowed}><RefreshCw size={14} />Refresh</button></div>
    <Messages error={error} />
    {!connected ? <div className="admin-empty"><ShieldCheck /><b>Connect an authorized identity session</b><span>Backup status is not available in unauthenticated preview mode.</span></div>
      : !allowed ? <div className="admin-empty"><b>Backup status not granted</b><span>This session does not include ops:backup:read.</span></div>
      : loading && !data ? <div className="admin-empty" role="status">Loading backup status...</div>
      : data && <div className="settings-grid" aria-label="Backup status">
        <section className="panel info-panel"><div className="panel-heading"><div><h2>Latest backup</h2><p>{data.configured ? "Read from the scheduler status file" : "Not configured"}</p></div></div>
          <div className="data-line"><span>Healthy</span><b>{data.ok ? "Yes" : "No"}</b></div>
          {data.reason && <div className="data-line"><span>Reason</span><b>{data.reason}</b></div>}
          <div className="data-line"><span>Last success</span><b>{stamp(data.last_success_at)}</b></div>
          <div className="data-line"><span>Age (hours)</span><b>{data.age_hours ?? "-"}{data.limit_hours ? ` of ${data.limit_hours} allowed` : ""}</b></div>
          <div className="data-line"><span>Last artifact</span><b>{data.last_artifact || "-"}</b></div></section></div>}
  </section></div>
  <RegisterWorkspace name="Recovery plans" types={["recovery_plan"]} api={api} claims={claims} connected={connected} /></>;
}
