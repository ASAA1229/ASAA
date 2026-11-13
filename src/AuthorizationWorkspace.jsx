import { useCallback, useEffect, useState } from "react";
import { Check, KeyRound, Plus, RefreshCw, ShieldCheck, UserRound, X } from "lucide-react";

const has = (claims, permission) => Array.isArray(claims?.permissions) && claims.permissions.includes(permission);
const emptyForm = { role_code: "", name: "", description: "", scope_type: "Organization", permissions: "" };
const assignmentForm = { role_template_id: "", subject: "", scope_reference: "organization:", effective_from: "", effective_to: "", reason: "" };

export default function AuthorizationWorkspace({ api, claims = {}, connected, onChanged }) {
  const [roles, setRoles] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showRoleForm, setShowRoleForm] = useState(false);
  const [showAssignmentForm, setShowAssignmentForm] = useState(false);
  const [roleForm, setRoleForm] = useState(emptyForm);
  const [assignment, setAssignment] = useState(assignmentForm);
  const [reviewReasons, setReviewReasons] = useState({});
  const [decisions, setDecisions] = useState({});
  const [revokeReasons, setRevokeReasons] = useState({});

  const canReadRoles = has(claims, "authorization:role:read");
  const canReadAssignments = has(claims, "authorization:assignment:read");

  const load = useCallback(async () => {
    if (!connected) return;
    setBusy(true);
    setError("");
    try {
      const [roleRows, assignmentRows] = await Promise.all([
        canReadRoles ? api("/api/v1/authorization/roles") : Promise.resolve([]),
        canReadAssignments ? api("/api/v1/authorization/assignments") : Promise.resolve([])
      ]);
      setRoles(Array.isArray(roleRows) ? roleRows : []);
      setAssignments(Array.isArray(assignmentRows) ? assignmentRows : []);
    } catch (err) {
      setError(err.message || "Authorization records could not be loaded.");
    } finally {
      setBusy(false);
    }
  }, [api, connected, canReadRoles, canReadAssignments]);

  useEffect(() => { load(); }, [load]);

  const submit = async (path, method, payload, message) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, { method, body: JSON.stringify(payload) });
      setShowRoleForm(false);
      setShowAssignmentForm(false);
      setRoleForm(emptyForm);
      setAssignment(assignmentForm);
      setNotice(message);
      await load();
      await onChanged?.();
    } catch (err) {
      setError(err.message || "The authorization change could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const createRole = event => {
    event.preventDefault();
    const permissions = roleForm.permissions.split(/[\n,]/).map(value => value.trim()).filter(Boolean);
    if (!permissions.length) {
      setError("Add at least one explicit permission identifier.");
      return;
    }
    if (new Set(permissions).size !== permissions.length || permissions.some(value => value.includes("*"))) {
      setError("Permissions must be unique explicit identifiers; wildcards are not allowed.");
      return;
    }
    submit("/api/v1/authorization/roles", "POST", {
      role_code: roleForm.role_code.trim(),
      name: roleForm.name.trim(),
      description: roleForm.description.trim() || null,
      scope_type: roleForm.scope_type,
      permissions
    }, "Role template submitted for independent approval.");
  };

  const createAssignment = event => {
    event.preventDefault();
    try {
      const effectiveFrom = new Date(assignment.effective_from);
      const effectiveTo = assignment.effective_to ? new Date(assignment.effective_to) : null;
      if (Number.isNaN(effectiveFrom.getTime()) || (effectiveTo && Number.isNaN(effectiveTo.getTime()))) {
        setError("Enter valid effective dates.");
        return;
      }
      submit("/api/v1/authorization/assignments", "POST", {
        role_template_id: assignment.role_template_id,
        subject: assignment.subject.trim(),
        scope_reference: assignment.scope_reference.trim(),
        effective_from: effectiveFrom.toISOString(),
        effective_to: effectiveTo?.toISOString() || null,
        reason: assignment.reason.trim()
      }, "Access assignment submitted for independent approval.");
    } catch {
      setError("The effective date range is invalid.");
    }
  };

  const review = (kind, row) => {
    const reason = (reviewReasons[row.id] || "").trim();
    if (reason.length < 3) return;
    const decision = decisions[row.id] || "Approve";
    const path = kind === "role"
      ? `/api/v1/authorization/roles/${row.id}/review`
      : `/api/v1/authorization/assignments/${row.id}/review`;
    submit(path, "POST", { expected_version: row.version, decision, reason },
      `${kind === "role" ? "Role" : "Access assignment"} ${decision.toLowerCase()}d.`);
  };

  const revoke = row => {
    const reason = (revokeReasons[row.id] || "").trim();
    if (reason.length < 3) return;
    submit(`/api/v1/authorization/assignments/${row.id}/revoke`, "POST",
      { expected_version: row.version, reason }, "Access assignment revoked in the application register.");
  };

  return <div className="admin-workspace">
    <section className="panel list-panel">
      <div className="list-heading">
        <div><h2>Identity & access governance</h2><p>Propose least-privilege role templates and manage scoped access assignments through independent review.</p></div>
        <button className="btn btn-quiet" onClick={load} disabled={!connected || busy}><RefreshCw size={14}/>Refresh</button>
      </div>
      {error && <div className="notice" role="alert">{error}</div>}
      {notice && <div className="admin-success" role="status"><Check size={15}/>{notice}</div>}
      {!connected && <div className="admin-empty"><ShieldCheck/><b>Connect an authorized identity session</b><span>Authorization records are unavailable in preview mode.</span></div>}
      {connected && <>
        <div className="admin-section-heading">
          <div><KeyRound/><h3>Role templates</h3></div>
          {has(claims, "authorization:role:write") && <button className="btn btn-primary" onClick={() => {setRoleForm(emptyForm);setShowRoleForm(true);}}><Plus size={14}/>Propose role</button>}
        </div>
        {!canReadRoles && <div className="admin-empty"><ShieldCheck/><b>Role register access not granted</b><span>This session does not include authorization:role:read.</span></div>}
        {canReadRoles && <div className="admin-tree-list">
          {roles.map(role => <div className="admin-tree-row" key={role.id}>
            <span className="admin-type">{role.scope_type}</span>
            <span className="admin-unit-copy"><b>{role.name} <small>({role.role_code})</small></b><small>{role.description || "No description"} · {role.permissions.length} explicit permissions · v{role.version}</small><small>{role.permissions.join(", ")}</small></span>
            <span className={`status status-${(role.status || "unknown").toLowerCase().replaceAll(" ", "-")}`}>{role.status}</span>
            {role.status === "Proposed" && role.created_by !== claims.sub && has(claims, "authorization:role:approve") && <div className="admin-review-controls">
              <input aria-label={`Review reason for ${role.role_code}`} placeholder="Independent review reason" value={reviewReasons[role.id] || ""} onChange={e=>setReviewReasons(current=>({...current,[role.id]:e.target.value}))}/>
              <select aria-label={`Decision for ${role.role_code}`} value={decisions[role.id] || "Approve"} onChange={e=>setDecisions(current=>({...current,[role.id]:e.target.value}))}><option>Approve</option><option>Reject</option></select>
              <button className="btn btn-primary" disabled={busy || (reviewReasons[role.id] || "").trim().length < 3} onClick={()=>review("role",role)}>Record decision</button>
            </div>}
          </div>)}
          {!roles.length && <div className="admin-empty"><KeyRound/><b>No role templates registered</b><span>Proposed roles require approval by a different authorized reviewer before assignment.</span></div>}
        </div>}
        {showRoleForm && <form className="admin-form" onSubmit={createRole}>
          <h3>Propose authorization role</h3>
          <label>Role code<input required pattern="[a-z][a-z0-9_.-]+" maxLength="80" value={roleForm.role_code} onChange={e=>setRoleForm(current=>({...current,role_code:e.target.value}))}/></label>
          <label>Role name<input required minLength="2" maxLength="160" value={roleForm.name} onChange={e=>setRoleForm(current=>({...current,name:e.target.value}))}/></label>
          <label>Description<input maxLength="1000" value={roleForm.description} onChange={e=>setRoleForm(current=>({...current,description:e.target.value}))}/></label>
          <label>Scope<select value={roleForm.scope_type} onChange={e=>setRoleForm(current=>({...current,scope_type:e.target.value}))}>{["Organization","Department","Project","Record"].map(value=><option key={value}>{value}</option>)}</select></label>
          <label>Explicit permissions (one per line or comma-separated)<textarea required rows="6" value={roleForm.permissions} onChange={e=>setRoleForm(current=>({...current,permissions:e.target.value}))} placeholder="supplier:read&#10;supplier:write"/></label>
          <p className="field-help">Wildcard permissions are blocked. The API independently validates every permission and enforces maker-checker approval.</p>
          <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={()=>setShowRoleForm(false)}><X size={14}/>Cancel</button><button className="btn btn-primary" disabled={busy}>Submit for approval</button></div>
        </form>}

        <div className="admin-section-heading">
          <div><UserRound/><h3>Access assignments</h3></div>
          {has(claims, "authorization:assignment:create") && <button className="btn btn-primary" onClick={() => {setAssignment(assignmentForm);setShowAssignmentForm(true);}}><Plus size={14}/>Request access</button>}
        </div>
        {!canReadAssignments && <div className="admin-empty"><ShieldCheck/><b>Assignment register access not granted</b><span>This session does not include authorization:assignment:read.</span></div>}
        {canReadAssignments && <div className="admin-tree-list">
          {assignments.map(item => {
            const role = roles.find(value => value.id === item.role_template_id);
            return <div className="admin-tree-row" key={item.id}>
              <span className="admin-type">{role?.role_code || "Role"}</span>
              <span className="admin-unit-copy"><b>{item.subject}</b><small>{item.scope_reference} · {item.effective_from ? new Date(item.effective_from).toLocaleString() : "No start date"}{item.effective_to ? ` – ${new Date(item.effective_to).toLocaleString()}` : " · No end date"}</small><small>{item.reason} · Requested by {item.created_by}</small></span>
              <span className={`status status-${(item.status || "unknown").toLowerCase().replaceAll(" ", "-")}`}>{item.status}</span>
              {item.status === "Pending Approval" && ![item.created_by,item.subject].includes(claims.sub) && has(claims, "authorization:assignment:approve") && <div className="admin-review-controls">
                <input aria-label={`Review reason for ${item.subject}`} placeholder="Independent review reason" value={reviewReasons[item.id] || ""} onChange={e=>setReviewReasons(current=>({...current,[item.id]:e.target.value}))}/>
                <select aria-label={`Decision for ${item.subject}`} value={decisions[item.id] || "Approve"} onChange={e=>setDecisions(current=>({...current,[item.id]:e.target.value}))}><option>Approve</option><option>Reject</option></select>
                <button className="btn btn-primary" disabled={busy || (reviewReasons[item.id] || "").trim().length < 3} onClick={()=>review("assignment",item)}>Record decision</button>
              </div>}
              {item.status === "Approved" && has(claims, "authorization:assignment:revoke") && <div className="admin-review-controls">
                <input aria-label={`Revocation reason for ${item.subject}`} placeholder="Revocation reason" value={revokeReasons[item.id] || ""} onChange={e=>setRevokeReasons(current=>({...current,[item.id]:e.target.value}))}/>
                <button className="btn btn-quiet" disabled={busy || (revokeReasons[item.id] || "").trim().length < 3} onClick={()=>revoke(item)}>Revoke</button>
              </div>}
            </div>;
          })}
          {!assignments.length && <div className="admin-empty"><UserRound/><b>No access assignments registered</b><span>Only active role templates can be assigned. New assignments remain pending until independently approved.</span></div>}
        </div>}
        {showAssignmentForm && <form className="admin-form" onSubmit={createAssignment}>
          <h3>Request scoped access</h3>
          <label>Active role template<select required value={assignment.role_template_id} onChange={e=>{const role=roles.find(value=>value.id===e.target.value);setAssignment(current=>({...current,role_template_id:e.target.value,scope_reference:role ? `${role.scope_type.toLowerCase()}:` : current.scope_reference}));}}><option value="">Select active role</option>{roles.filter(role=>role.status==="Active").map(role=><option key={role.id} value={role.id}>{role.name} · {role.scope_type}</option>)}</select></label>
          <label>Subject identity ID<input required maxLength="128" value={assignment.subject} onChange={e=>setAssignment(current=>({...current,subject:e.target.value}))}/></label>
          <label>Scope reference<input required maxLength="300" value={assignment.scope_reference} onChange={e=>setAssignment(current=>({...current,scope_reference:e.target.value}))}/></label>
          <label>Effective from<input required type="datetime-local" value={assignment.effective_from} onChange={e=>setAssignment(current=>({...current,effective_from:e.target.value}))}/></label>
          <label>Effective to (optional)<input type="datetime-local" value={assignment.effective_to} onChange={e=>setAssignment(current=>({...current,effective_to:e.target.value}))}/></label>
          <label>Business justification<textarea required minLength="3" maxLength="1000" rows="3" value={assignment.reason} onChange={e=>setAssignment(current=>({...current,reason:e.target.value}))}/></label>
          <p className="field-help">The scope prefix must match the role scope. Assignments require independent approval and cannot be approved by the requester or assigned subject.</p>
          <div className="modal-actions"><button type="button" className="btn btn-quiet" onClick={()=>setShowAssignmentForm(false)}><X size={14}/>Cancel</button><button className="btn btn-primary" disabled={busy || !roles.some(role=>role.id===assignment.role_template_id && role.status==="Active")}>Submit access request</button></div>
        </form>}
      </>}
    </section>
  </div>;
}
