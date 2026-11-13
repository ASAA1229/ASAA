import { useEffect, useState } from "react";
import { Building2, Check, ChevronRight, Database, Plus, RefreshCw, ShieldCheck, Users, X } from "lucide-react";

const permission = (claims, value) => Array.isArray(claims.permissions) && claims.permissions.includes(value);
const empty = { organization: null, units: [], domains: [], records: [], campaigns: [] };

export default function AdministrationWorkspace({ name, api, claims = {}, connected, onChanged }) {
  const [data, setData] = useState(empty);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({});
  const [showForm, setShowForm] = useState(false);
  const [showRecordForm, setShowRecordForm] = useState(false);
  const [recordDomain, setRecordDomain] = useState("");
  const [decisionReason, setDecisionReason] = useState({});
  const [decision, setDecision] = useState({});
  const [tab, setTab] = useState("Records");

  const load = async () => {
    if (!connected) return;
    setBusy(true); setError("");
    const jobs = [];
    if (name === "Organization & entities" || name === "Departments & teams") {
      jobs.push(["organization", api("/api/v1/administration/profile")]);
      jobs.push(["units", api("/api/v1/administration/units")]);
    }
    if (name === "Master data") jobs.push(["domains", api("/api/v1/master-data/domains")]);
    if (name === "Identity & access" || name === "Access reviews") jobs.push(["campaigns", api("/api/v1/administration/access-reviews")]);
    try {
      const pairs = await Promise.all(jobs.map(async ([key, promise]) => [key, await promise]));
      setData(current => ({ ...current, ...Object.fromEntries(pairs) }));
    } catch (err) { setError(err.message || "Administration records could not be loaded."); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); }, [name, connected]);

  const submit = async (path, method, payload, message) => {
    setBusy(true); setError(""); setNotice("");
    try {
      await api(path, { method, body: JSON.stringify(payload) });
      setShowForm(false); setShowRecordForm(false); setForm({}); setNotice(message); await load(); await onChanged?.();
    } catch (err) { setError(err.message || "The change could not be saved."); }
    finally { setBusy(false); }
  };
  const field = (key, label, type = "text", required = true) => <label key={key}>{label}<input type={type} required={required} value={form[key] || ""} onChange={e => setForm(current => ({ ...current, [key]: e.target.value }))}/></label>;

  const profile = name === "Organization & entities";
  const structure = name === "Departments & teams";
  const master = name === "Master data";
  const identity = name === "Identity & access" || name === "Access reviews";

  return <div className="admin-workspace">
    <section className="panel list-panel">
      <div className="list-heading"><div><h2>{name}</h2><p>{profile ? "Organization profile and legal-entity establishment gates." : structure ? "Configurable hierarchy, departments, teams, positions and locations." : master ? "Authoritative domains, stewardship and duplicate reference governance." : "Review identity access snapshots and record independent recertification decisions."}</p></div><button className="btn btn-quiet" onClick={load} disabled={busy}><RefreshCw size={14}/>Refresh</button></div>
      {error && <div className="notice">{error}</div>}{notice && <div className="admin-success"><Check size={15}/>{notice}</div>}
      {!connected && <div className="admin-empty"><ShieldCheck/><b>Connect an authorized identity session</b><span>Administration data is not available in unauthenticated preview mode.</span></div>}
      {connected && profile && <>
        <div className="admin-section-heading"><div><Building2/><h3>Organization profile</h3></div>{permission(claims,"organization:profile:write") && <button className="btn btn-primary" onClick={() => { setForm(data.organization ? { ...data.organization } : { display_name: "ASAA", lifecycle_status: "Pre-Incorporation" }); setShowForm(true); }}> {data.organization ? "Edit profile" : "Create profile"}</button>}</div>
        {data.organization ? <div className="admin-detail-grid">{[["Display name",data.organization.display_name],["Legal name",data.organization.legal_name],["Lifecycle",data.organization.lifecycle_status],["Country",data.organization.country_code],["Timezone",data.organization.timezone],["Website",data.organization.website],["Registration reference",data.organization.registration_reference],["Version",data.organization.version]].map(([k,v])=><div key={k}><small>{k}</small><b>{v || "Not recorded"}</b></div>)}</div> : <div className="admin-empty"><Building2/><b>No organization profile registered</b><span>Registration and legal status must be explicitly confirmed; no incorporation status is inferred.</span></div>}
        {showForm && <form className="admin-form" onSubmit={e => { e.preventDefault(); const payload = { ...form }; const expected = data.organization?.version; if (expected) payload.expected_version = expected; submit("/api/v1/administration/profile", expected ? "PATCH" : "PUT", payload, "Organization profile saved."); }}>
          <h3>{data.organization ? "Edit organization profile" : "Register organization profile"}</h3>{field("display_name","Display name")}{field("legal_name","Legal name", "text", false)}
          <label>Lifecycle status<select value={form.lifecycle_status || "Pre-Incorporation"} onChange={e => setForm(current => ({...current,lifecycle_status:e.target.value}))}><option>Pre-Incorporation</option><option>Active</option><option>Dormant</option></select></label>
          {field("country_code","Country code (ISO 3166-1 alpha-2)","text",false)}{field("timezone","Time zone (IANA)","text",false)}{field("website","Website","url",false)}{field("registration_reference","Registration reference","text",false)}
          <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={() => setShowForm(false)}>Cancel</button><button className="btn btn-primary" disabled={busy}>Save profile</button></div>
        </form>}
      </>}
      {connected && structure && <>
        <div className="admin-section-heading"><div><Users/><h3>Organization structure</h3></div>{permission(claims,"organization:structure:write") && <button className="btn btn-primary" onClick={() => {setForm({unit_type:"Department"});setShowForm(true);}}> <Plus size={14}/>Add unit</button>}</div>
        <div className="admin-tree-list">{data.units.map(unit => <div className="admin-tree-row" key={unit.id}><span className="admin-type">{unit.unit_type}</span><span className="admin-unit-copy"><b>{unit.name}</b><small>{unit.unit_code} · {unit.owner_subject || "No owner assigned"} · {unit.effective_from || "No start date"}</small></span><span className={`status status-${unit.status.toLowerCase()}`}>{unit.status}</span>{permission(claims,"organization:structure:write") && unit.status !== "Active" && <button className="btn btn-quiet" onClick={() => submit(`/api/v1/administration/units/${unit.id}`,"PATCH",{expected_version:unit.version,status:"Active"},"Organization unit activated.")}>Activate</button>}</div>)}{!data.units.length && <div className="admin-empty"><Users/><b>No structure units registered</b><span>Create only the entities, departments and teams that have actually been approved.</span></div>}</div>
        {showForm && <form className="admin-form" onSubmit={e => {e.preventDefault();submit("/api/v1/administration/units","POST",form,"Organization unit created in Proposed status.");}}>
          <h3>Create organization unit</h3><label>Type<select value={form.unit_type || "Department"} onChange={e => setForm(current => ({...current,unit_type:e.target.value}))}>{["Legal Entity","Business Unit","Division","Department","Team","Location","Position"].map(v=><option key={v}>{v}</option>)}</select></label>
          <label>Parent unit<select value={form.parent_id || ""} onChange={e => setForm(current => ({...current,parent_id:e.target.value || null}))}><option value="">No parent (top-level)</option>{data.units.map(unit=><option key={unit.id} value={unit.id}>{unit.unit_type}: {unit.name}</option>)}</select></label>
          {field("unit_code","Unique unit code")}{field("name","Name")}{field("owner_subject","Owner subject (identity ID)","text",false)}{field("effective_from","Effective from","date",false)}{field("effective_to","Effective to","date",false)}
          <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={() => setShowForm(false)}>Cancel</button><button className="btn btn-primary" disabled={busy}>Create proposed unit</button></div>
        </form>}
      </>}
      {connected && master && <>
        <div className="admin-section-heading"><div><Database/><h3>Master-data domains</h3></div>{permission(claims,"masterdata:domain:write") && <button className="btn btn-primary" onClick={() => {setForm({});setShowForm(true);}}><Plus size={14}/>Register domain</button>}</div>
        <div className="admin-tree-list">{data.domains.map(domain => <button className="admin-domain-row" key={domain.id} onClick={async () => {setSelected(domain.id);setRecordDomain(domain.id);try{const rows=await api(`/api/v1/master-data/domains/${domain.id}/records`);setData(current=>({...current,records:rows}));}catch(e){setError(e.message);}}}><span><b>{domain.name}</b><small>{domain.domain_code} · {domain.authoritative_source}</small></span><span>{domain.owner_subject} / {domain.steward_subject}</span><ChevronRight/></button>)}</div>
        {showForm && <form className="admin-form" onSubmit={e => {e.preventDefault();submit("/api/v1/master-data/domains","POST",form,"Master-data domain registered.");}}><h3>Register domain</h3>{field("domain_code","Domain code")}{field("name","Domain name")}{field("authoritative_source","Authoritative source")}{field("owner_subject","Owner subject")}{field("steward_subject","Steward subject")}{field("description","Description","text",false)}<div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={()=>setShowForm(false)}>Cancel</button><button className="btn btn-primary" disabled={busy}>Save domain</button></div></form>}
        {selected && <div className="admin-records"><h3>Domain record references</h3><div className="admin-tree-list">{data.records.map(row=><div className="admin-tree-row" key={row.id}><span className="admin-unit-copy"><b>{row.record_type} · {row.record_id}</b><small>{row.source_system} / {row.source_record_id}</small></span><span className={`status status-${row.status.toLowerCase().replaceAll(" ","-")}`}>{row.status}</span></div>)}</div>{permission(claims,"masterdata:record:write") && <button className="btn btn-quiet" onClick={()=>{setForm({record_type:"",record_id:"",source_system:"",source_record_id:""});setShowRecordForm(true);}}>Register source reference</button>}</div>}
      </>}
        {showRecordForm && <form className="admin-form" onSubmit={e=>{e.preventDefault();submit("/api/v1/master-data/domains/"+recordDomain+"/records","POST",form,"Source reference registered. Duplicate candidates require steward review.");}}><h3>Register source reference</h3>{field("record_type","Record type")}{field("record_id","Internal record ID")}{field("source_system","Source system")}{field("source_record_id","Source record ID")}<div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={()=>setShowRecordForm(false)}>Cancel</button><button className="btn btn-primary" disabled={busy}>Register reference</button></div></form>}
      {connected && identity && <>
        <div className="admin-section-heading"><div><ShieldCheck/><h3>Access review campaigns</h3></div>{permission(claims,"identity:access-review:create") && <button className="btn btn-primary" onClick={()=>{setForm({items:[{subject:"",permission_snapshot:"",scope_reference:"organization"}]});setShowForm(true);}}><Plus size={14}/>New review</button>}</div>
        <p className="field-help">Review campaigns use a dated snapshot supplied by an authorized identity export. Decisions are recorded here; they do not directly revoke provider permissions.</p>
        {data.campaigns.map(campaign=><section className="admin-campaign" key={campaign.id}><div><b>{campaign.title}</b><small>Snapshot: {new Date(campaign.snapshot_as_of).toLocaleString()} · Source: {campaign.source_reference}</small></div>{campaign.items.map(item=><div className="admin-review-item" key={item.id}><span><b>{item.subject}</b><small>{item.role_code || "No role label"} · {item.scope_reference} · {item.permission_snapshot.join(", ")}</small></span><span className={`status status-${item.decision.toLowerCase()}`}>{item.decision}</span>{item.decision === "Pending" && permission(claims,"identity:access-review:review") && item.subject !== claims.sub && <div className="admin-review-controls"><input placeholder="Review reason" value={decisionReason[item.id] || ""} onChange={e=>setDecisionReason(current=>({...current,[item.id]:e.target.value}))}/><select value={decision[item.id] || "Retain"} onChange={e=>setDecision(current=>({...current,[item.id]:e.target.value}))}><option>Retain</option><option>Modify</option><option>Revoke</option></select><button className="btn btn-primary" disabled={busy || (decisionReason[item.id]||"").trim().length<3} onClick={()=>submit(`/api/v1/administration/access-reviews/items/${item.id}/decision`,"POST",{expected_version:item.version,decision:decision[item.id]||"Retain",reason:decisionReason[item.id]},"Access review decision recorded.")}>Record</button></div>}</div>)}</section>)}
        {!data.campaigns.length && <div className="admin-empty"><ShieldCheck/><b>No access reviews registered</b><span>Import a dated identity-provider access export to begin recertification. No users or grants are invented.</span></div>}
        {showForm && <form className="admin-form" onSubmit={e=>{e.preventDefault();let items;try{items=JSON.parse(form.items_json);}catch{setError("Items must be valid JSON.");return;}submit("/api/v1/administration/access-reviews","POST",{title:form.title,source_reference:form.source_reference,snapshot_as_of:form.snapshot_as_of,due_at:form.due_at || null,items},"Access review campaign created.");}}><h3>New access review campaign</h3>{field("title","Campaign title")}{field("source_reference","Identity export reference")}{field("snapshot_as_of","Snapshot date/time","datetime-local")}{field("due_at","Due date/time","datetime-local",false)}<label>Access snapshot items (JSON)<textarea rows="8" value={form.items_json || '[{"subject":"user-id","role_code":"role","permission_snapshot":["permission:read"],"scope_reference":"organization:org-id","justification":"Business need"}]'} onChange={e=>setForm(current=>({...current,items_json:e.target.value}))}/></label><div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={()=>setShowForm(false)}>Cancel</button><button className="btn btn-primary" disabled={busy}>Create campaign</button></div></form>}
      </>}
    </section>
  </div>;
}
