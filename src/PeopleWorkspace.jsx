import { useCallback, useEffect, useRef, useState } from "react";
import { Users, UserPlus, CalendarDays, ClipboardList, ShieldCheck, RefreshCw, CheckCircle2, AlertCircle, Laptop, LogOut } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);
const dateText = value => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const statusClass = value => "status status-" + String(value || "unknown").toLowerCase().replaceAll(" ", "-");

export default function PeopleWorkspace({ name, api, claims, connected, onChanged }) {
  const [data, setData] = useState({ employees: [], templates: [], assignments: [], leave: [], exits: [], assets: [] });
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [editingEmployeeId, setEditingEmployeeId] = useState("");
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [assets, setAssets] = useState([]);
  const [history, setHistory] = useState([]);
  const apiRef = useRef(api);
  const changedRef = useRef(onChanged);
  apiRef.current = api;
  changedRef.current = onChanged;
  const permissions = Array.isArray(claims?.permissions) ? claims.permissions : [];
  const can = permission => permissions.includes(permission);
  const permissionKey = permissions.slice().sort().join("|");

  const load = useCallback(async () => {
    if (!connected) return;
    setLoading(true);
    setError("");
    const next = { employees: [], templates: [], assignments: [], leave: [], exits: [], assets: [] };
    const jobs = [];
    const employeeViews = ["People directory", "Employment lifecycle", "Onboarding", "Offboarding", "Leave management", "Employee assets"];
    if (employeeViews.includes(name) && can("hr:employee:read")) jobs.push(["employees", "/api/v1/hr/employees"]);
    if (name === "Onboarding" && can("onboarding:read")) {
      jobs.push(["templates", "/api/v1/onboarding/templates"]);
      jobs.push(["assignments", "/api/v1/onboarding/assignments"]);
    }
    if (name === "Offboarding") {
      if (can("hr:exit:read")) jobs.push(["exits", "/api/v1/hr/exit-cases"]);
      if (can("onboarding:read")) {
        jobs.push(["templates", "/api/v1/onboarding/templates"]);
        jobs.push(["assignments", "/api/v1/onboarding/assignments"]);
      }
    }
    if (name === "Leave management" && can("hr:leave:read")) jobs.push(["leave", "/api/v1/hr/leave-requests"]);
    const results = await Promise.all(jobs.map(async ([key, path]) => {
      try { return [key, await apiRef.current(path), ""]; }
      catch (e) { return [key, [], e.message]; }
    }));
    const failures = [];
    for (const [key, value, message] of results) {
      next[key] = Array.isArray(value) ? value : [];
      if (message) failures.push(key + ": " + message);
    }
    setData(next);
    if (failures.length) setError(failures.join(" · "));
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- 'can' derives from 'permissions'
  }, [connected, name, permissionKey]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!selectedEmployeeId && data.employees.length) setSelectedEmployeeId(data.employees[0].id);
  }, [data.employees, selectedEmployeeId]);

  const run = async (path, method, payload, message) => {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRef.current(path, { method, ...(payload === undefined ? {} : { body: JSON.stringify(payload) }) });
      setNotice(message);
      setForm({});
      if (name === "People directory") setEditingEmployeeId("");
      await load();
      if (changedRef.current) await changedRef.current();
      if (name === "Employment lifecycle" && selectedEmployeeId && can("hr:employee:read")) {
        const rows = await apiRef.current("/api/v1/hr/employees/" + selectedEmployeeId + "/employment-records");
        setHistory(rows);
      }
      if (name === "Employee assets" && selectedEmployeeId && can("hr:asset:read")) {
        setAssets(await apiRef.current("/api/v1/hr/employees/" + selectedEmployeeId + "/assets"));
      }
    } catch (e) { setError(e.message || "The request could not be completed."); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    if (name === "Employment lifecycle" && selectedEmployeeId && connected && can("hr:employee:read")) {
      apiRef.current("/api/v1/hr/employees/" + selectedEmployeeId + "/employment-records").then(setHistory).catch(e => setError(e.message));
    } else setHistory([]);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- 'can' derives from 'permissions'
  }, [name, selectedEmployeeId, connected, permissionKey]);

  useEffect(() => {
    if (name === "Employee assets" && selectedEmployeeId && connected && can("hr:asset:read")) {
      apiRef.current("/api/v1/hr/employees/" + selectedEmployeeId + "/assets").then(setAssets).catch(e => setError(e.message));
    } else setAssets([]);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- 'can' derives from 'permissions'
  }, [name, selectedEmployeeId, connected, permissionKey]);

  const field = (key, label, type = "text", required = true) => (
    <label className="people-field" key={key}>{label}
      <input type={type} required={required} value={form[key] ?? ""} onChange={e => setForm(current => ({ ...current, [key]: e.target.value }))}/>
    </label>
  );
  const selectField = (key, label, options, required = true) => (
    <label className="people-field" key={key}>{label}
      <select required={required} value={form[key] ?? ""} onChange={e => setForm(current => ({ ...current, [key]: e.target.value }))}>
        <option value="">Select…</option>{options.map(option => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  );
  const submit = (event, path, method, payload, message) => {
    event.preventDefault();
    run(path, method, payload, message);
  };
  const employee = data.employees.find(item => item.id === selectedEmployeeId);

  if (!connected) return <section className="people-panel"><Empty icon={Users} title="Connect an authorized session" text="HR records are not shown in preview mode."/></section>;

  return <div className="people-workspace">
    <div className="people-statusbar">
      <div><span className="status-dot online"/><b>Connected HR records</b><small>Organization-scoped API data</small></div>
      <button className="btn btn-quiet" onClick={load} disabled={loading}><RefreshCw size={14}/>{loading ? "Refreshing…" : "Refresh"}</button>
    </div>
    {notice && <div className="people-notice success"><CheckCircle2 size={16}/>{notice}</div>}
    {error && <div className="people-notice error"><AlertCircle size={16}/>{error}</div>}

    {name === "People directory" && <>
      <section className="people-panel">
        <PanelHeading icon={Users} title="Employee directory" subtitle="Authoritative employee records and current lifecycle state" count={data.employees.length}/>
        {can("hr:employee:write") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/hr/employees", "POST", {
          employee_code: form.employee_code || null, first_name: form.first_name, last_name: form.last_name,
          work_email: form.work_email || null, employment_type: form.employment_type || "Employee",
          hire_date: form.hire_date || null
        }, "Employee record created.")}>
          {field("employee_code", "Employee code", "text", false)}{field("first_name", "First name")}{field("last_name", "Last name")}
          {field("work_email", "Work email", "email", false)}{selectField("employment_type", "Employment type", ["Employee", "Contractor", "Intern", "Consultant"])}
          {field("hire_date", "Hire date", "date", false)}
          <button className="btn btn-primary" disabled={busy}><UserPlus size={14}/>Add employee</button>
        </form>}
        {editingEmployeeId && can("hr:employee:write") && (()=>{const selected=data.employees.find(x=>x.id===editingEmployeeId);return selected?<form className="people-form" onSubmit={e=>submit(e,"/api/v1/hr/employees/"+editingEmployeeId,"PATCH",{employee_code:form.employee_code??selected.employee_code,first_name:form.first_name,last_name:form.last_name,preferred_name:form.preferred_name||null,work_email:form.work_email||null,work_phone:form.work_phone||null},"Employee profile updated.")}><h3>Edit employee profile</h3>{field("employee_code","Employee code","text",false)}{field("first_name","First name")}{field("last_name","Last name")}{field("preferred_name","Preferred name","text",false)}{field("work_email","Work email","email",false)}{field("work_phone","Work phone","text",false)}<button className="btn btn-primary" disabled={busy}>Save profile</button><button type="button" className="btn btn-quiet" onClick={()=>{setEditingEmployeeId("");setForm({});}}>Cancel</button></form>:null})()}
        {!can("hr:employee:read") ? <Empty icon={ShieldCheck} title="Directory access not granted" text="This session does not include hr:employee:read."/> :
          <div className="people-table-wrap" tabIndex={0} role="region" aria-label="Scrollable data table"><table className="people-table"><thead><tr><th>Employee</th><th>Code</th><th>Employment</th><th>Hire date</th><th>Status</th><th>Actions</th></tr></thead><tbody>
            {data.employees.map(item => <tr key={item.id}><td><b>{item.first_name} {item.last_name}</b><small>{item.work_email || "No work email"}</small></td><td>{item.employee_code || "—"}</td><td>{item.employment_type}</td><td>{dateText(item.hire_date)}</td><td><span className={statusClass(item.status)}>{item.status}</span></td><td>{can("hr:employee:write")&&<button className="btn btn-quiet" onClick={()=>{setEditingEmployeeId(item.id);setForm({employee_code:item.employee_code||"",first_name:item.first_name,last_name:item.last_name,preferred_name:item.preferred_name||"",work_email:item.work_email||"",work_phone:item.work_phone||""});}}>Edit</button>}</td></tr>)}
          </tbody></table>{!data.employees.length && <Empty icon={Users} title="No employee records" text="Create an employee record when authorized and supported by the approved HR process."/>}</div>}
      </section>
    </>}

    {name === "Employment lifecycle" && <>
      <section className="people-panel">
        <PanelHeading icon={Users} title="Employment lifecycle" subtitle="Effective-dated employment history and controlled status transitions"/>
        {can("hr:employee:read") && <EmployeePicker employees={data.employees} value={selectedEmployeeId} onChange={setSelectedEmployeeId}/>}
        {employee && <div className="people-employee-card"><div><b>{employee.first_name} {employee.last_name}</b><small>{employee.employee_code || employee.id} · {employee.employment_type}</small></div><span className={statusClass(employee.status)}>{employee.status}</span></div>}
        {employee && can("hr:employee:lifecycle") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/hr/employees/" + employee.id + "/lifecycle", "POST", {
          status: form.status, effective_from: form.effective_from || today(), reason: form.reason
        }, "Employment lifecycle transition recorded.")}>
          {selectField("status", "New lifecycle status", ({Preboarding:["Active"],Active:["On Leave","Suspended"],"On Leave":["Active","Suspended"],Suspended:["Active"]})[employee.status] || [])}
          {field("effective_from", "Effective from", "date")}{field("reason", "Reason")}
          <button className="btn btn-primary" disabled={busy || !form.status}><CheckCircle2 size={14}/>Record transition</button>
        </form>}
        {employee && can("hr:employment:write") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/hr/employees/" + employee.id + "/employment-records", "POST", {
          department_id: form.department_id || null, position_title: form.position_title || null,
          manager_employee_id: form.manager_employee_id || null, work_location: form.work_location || null,
          employment_type: form.record_employment_type || employee.employment_type,
          status: form.record_status || "Active", effective_from: form.record_effective_from || today(),
          effective_to: form.record_effective_to || null, reason: form.record_reason || null
        }, "Employment record added to history.")}>
          <h3>Add employment record</h3>{field("department_id", "Department reference", "text", false)}{field("position_title", "Position title", "text", false)}
          {field("manager_employee_id", "Manager employee ID", "text", false)}{field("work_location", "Work location", "text", false)}
          <label className="people-field">Employment type<select value={form.record_employment_type || employee.employment_type} onChange={e => setForm(current => ({ ...current, record_employment_type: e.target.value }))}>{["Employee","Contractor","Intern","Consultant"].map(v=><option key={v}>{v}</option>)}</select></label>
          <label className="people-field">Record status<select value={form.record_status || "Active"} onChange={e => setForm(current => ({ ...current, record_status: e.target.value }))}>{["Preboarding","Active","On Leave","Suspended"].map(v=><option key={v}>{v}</option>)}</select></label>
          {field("record_effective_from", "Effective from", "date", false)}{field("record_effective_to", "Effective to", "date", false)}{field("record_reason", "Reason", "text", false)}
          <button className="btn btn-primary" disabled={busy}>Add employment record</button>
        </form>}
        <h3>Employment history</h3>
        {history.length ? <div className="people-history">{history.map(row=><div key={row.id}><span className="people-timeline-dot"/><div><b>{row.position_title || "Employment record"} · {row.status}</b><small>{dateText(row.effective_from)} – {dateText(row.effective_to)} · {row.employment_type}</small><p>{row.reason || "No reason recorded"}</p></div></div>)}</div> : <Empty icon={ClipboardList} title="No employment history loaded" text="Select an employee with directory access to review their effective-dated records."/>}
      </section>
    </>}

    {name === "Onboarding" && <>
      <section className="people-panel">
        <PanelHeading icon={ClipboardList} title="Onboarding templates" subtitle="Create versioned checklists and assign tasks to employees" count={data.templates.length}/>
        {can("onboarding:template:write") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/onboarding/templates", "POST", {
          template_code: form.template_code, name: form.name, workflow_type: "Onboarding",
          tasks: [{ title: form.task_title, description: form.task_description || null, owner_role: form.owner_role, required: form.required !== "false", sequence: 1 }]
        }, "Onboarding template created.")}>
          {field("template_code", "Template code")}{field("name", "Template name")}{field("task_title", "First task title")}{field("task_description", "Task description", "text", false)}
          {field("owner_role", "Task owner role")}<label className="people-field">Required task<select value={form.required ?? "true"} onChange={e => setForm(current => ({ ...current, required: e.target.value }))}><option value="true">Required</option><option value="false">Optional</option></select></label>
          <button className="btn btn-primary" disabled={busy}>Create template</button>
        </form>}
        <div className="people-card-grid">{data.templates.filter(x => x.workflow_type === "Onboarding").map(item=><article className="people-record-card" key={item.id}><div><b>{item.name}</b><span className={statusClass(item.active ? "Active" : "Inactive")}>{item.active ? "Active" : "Inactive"}</span></div><small>{item.template_code} · v{item.version}</small><p>{item.tasks?.length || 0} checklist tasks</p></article>)}</div>
      </section>
      <section className="people-panel">
        <PanelHeading icon={Users} title="Onboarding assignments" subtitle="Employee checklist progress" count={data.assignments.length}/>
        {can("onboarding:assignment:write") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/onboarding/assignments", "POST", { employee_id: form.assignment_employee, template_id: form.assignment_template, target_date: form.assignment_target || null }, "Onboarding checklist assigned.")}>
          {can("hr:employee:read") ? <label className="people-field">Employee<select required value={form.assignment_employee || ""} onChange={e => setForm(current => ({ ...current, assignment_employee: e.target.value }))}><option value="">Select employee…</option>{data.employees.map(x=><option key={x.id} value={x.id}>{x.employee_code || x.id} · {x.first_name} {x.last_name}</option>)}</select></label> : field("assignment_employee","Employee ID")}
          <label className="people-field">Template<select required value={form.assignment_template || ""} onChange={e => setForm(current => ({ ...current, assignment_template: e.target.value }))}><option value="">Select template…</option>{data.templates.filter(x=>x.workflow_type==="Onboarding"&&x.active).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          {field("assignment_target", "Target date", "date", false)}<button className="btn btn-primary" disabled={busy}>Assign onboarding</button>
        </form>}
        <div className="people-record-list">{data.assignments.map(item=><article className="people-record-card" key={item.id}><div><b>{data.employees.find(x=>x.id===item.employee_id)?.first_name || item.employee_id}</b><span className={statusClass(item.status)}>{item.status}</span></div><small>Target: {dateText(item.target_date)} · Template v{item.template_version}</small>
          {(item.tasks || []).map(task=><div className="people-task" key={task.id}><div><b>{task.title}</b><small>{task.owner_role} · {task.required ? "Required" : "Optional"}</small></div><span className={statusClass(task.status)}>{task.status}</span>{can("onboarding:task:update") && !["Completed","Waived"].includes(task.status) && <button className="btn btn-quiet" disabled={busy} onClick={()=>run("/api/v1/onboarding/tasks/"+task.id,"PATCH",{status:"Completed"},"Checklist task completed.")}>Mark complete</button>}</div>)}
        </article>)}</div>
      </section>
    </>}

    {name === "Offboarding" && <>
      <section className="people-panel">
        <PanelHeading icon={LogOut} title="Offboarding cases" subtitle="Exit checklist, asset return and employment closure gates" count={data.exits.length}/>
        {can("onboarding:template:write") && <form className="people-form" onSubmit={e=>submit(e,"/api/v1/onboarding/templates","POST",{template_code:form.exit_template_code,name:form.exit_template_name,workflow_type:"Offboarding",tasks:[{title:form.exit_task_title,description:form.exit_task_description||null,owner_role:form.exit_owner_role,required:true,sequence:1}]},"Offboarding checklist template created.")}>
          <h3>Create offboarding checklist template</h3>{field("exit_template_code","Template code")}{field("exit_template_name","Template name")}{field("exit_task_title","Required checklist task")}{field("exit_task_description","Task description","text",false)}{field("exit_owner_role","Task owner role")}
          <button className="btn btn-primary" disabled={busy}>Create offboarding template</button>
        </form>}
        {can("hr:exit:write") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/hr/employees/" + form.exit_employee + "/exit-cases", "POST", {
          planned_last_day: form.planned_last_day, reason_category: form.reason_category,
          notes: form.exit_notes || null, offboarding_template_id: form.offboarding_template_id || null
        }, "Offboarding case opened.")}>
          {can("hr:employee:read") ? <label className="people-field">Employee<select required value={form.exit_employee || ""} onChange={e => setForm(current => ({ ...current, exit_employee: e.target.value }))}><option value="">Select employee…</option>{data.employees.filter(x=>!["Inactive","Offboarding"].includes(x.status)).map(x=><option key={x.id} value={x.id}>{x.first_name} {x.last_name} · {x.employee_code || x.id}</option>)}</select></label> : field("exit_employee","Employee ID")}
          {field("planned_last_day", "Planned last day", "date")}{field("reason_category", "Reason category")}
          <label className="people-field">Offboarding checklist<select value={form.offboarding_template_id || ""} onChange={e => setForm(current => ({ ...current, offboarding_template_id: e.target.value }))}><option value="">No template selected</option>{data.templates.filter(x=>x.workflow_type==="Offboarding"&&x.active).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          {field("exit_notes", "Notes", "text", false)}<button className="btn btn-primary" disabled={busy}>Open exit case</button>
        </form>}
        <div className="people-record-list">{data.exits.map(item=><article className="people-record-card" key={item.id}><div><b>{data.employees.find(x=>x.id===item.employee_id)?.first_name || item.employee_id}</b><span className={statusClass(item.status)}>{item.status}</span></div><small>Last day: {dateText(item.planned_last_day)} · {item.reason_category}</small>
          {item.checklist_assignment_id && <div className="people-offboarding-tasks"><b>Required offboarding checklist</b>{(data.assignments.find(x=>x.id===item.checklist_assignment_id)?.tasks||[]).map(task=><div className="people-task" key={task.id}><div><b>{task.title}</b><small>{task.owner_role} · {task.required?"Required":"Optional"}</small></div><span className={statusClass(task.status)}>{task.status}</span>{can("onboarding:task:update")&&!["Completed","Waived"].includes(task.status)&&<button className="btn btn-quiet" disabled={busy} onClick={()=>run("/api/v1/onboarding/tasks/"+task.id,"PATCH",{status:"Completed"},"Offboarding checklist task completed.")}>Mark complete</button>}</div>)}</div>}
          {can("hr:exit:complete")&&item.status==="Open"&&<button className="btn btn-quiet" disabled={busy} onClick={()=>run("/api/v1/hr/exit-cases/"+item.id+"/complete","POST",undefined,"Exit case completed after server-side closure checks.")}>Complete exit case</button>}</article>)}</div>
      </section>
    </>}

    {name === "Leave management" && <>
      <section className="people-panel">
        <PanelHeading icon={CalendarDays} title="Leave management" subtitle="Requests and independent manager review; no unconfigured balance or accrual is assumed" count={data.leave.length}/>
        {can("hr:leave:request") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/hr/employees/" + form.leave_employee + "/leave-requests", "POST", {
          leave_category: form.leave_category, start_date: form.leave_start, end_date: form.leave_end, reason: form.leave_reason || null
        }, "Leave request submitted for review.")}>
          {can("hr:employee:read") ? <label className="people-field">Employee<select required value={form.leave_employee || ""} onChange={e => setForm(current => ({ ...current, leave_employee: e.target.value }))}><option value="">Select employee…</option>{data.employees.map(x=><option key={x.id} value={x.id}>{x.first_name} {x.last_name} · {x.employee_code || x.id}</option>)}</select></label> : field("leave_employee","Employee ID")}
          {field("leave_category", "Leave category")}{field("leave_start", "Start date", "date")}{field("leave_end", "End date", "date")}{field("leave_reason", "Reason", "text", false)}
          <button className="btn btn-primary" disabled={busy}>Submit leave request</button>
        </form>}
        <div className="people-table-wrap" tabIndex={0} role="region" aria-label="Scrollable data table"><table className="people-table"><thead><tr><th>Employee</th><th>Leave type</th><th>Dates</th><th>Status</th><th>Decision</th></tr></thead><tbody>
          {data.leave.map(item=><tr key={item.id}><td>{data.employees.find(x=>x.id===item.employee_id)?.first_name || item.employee_id}</td><td>{item.leave_category}</td><td>{dateText(item.start_date)} – {dateText(item.end_date)}</td><td><span className={statusClass(item.status)}>{item.status}</span></td><td>{item.status==="Submitted"&&can("hr:leave:review")?<div className="people-inline-actions"><button className="btn btn-quiet" disabled={busy||item.created_by===claims.sub} onClick={()=>run("/api/v1/hr/leave-requests/"+item.id+"/review","POST",{decision:"Approved",review_note:"Reviewed in HR workspace"},"Leave request approved.")}>Approve</button><button className="btn btn-quiet" disabled={busy||item.created_by===claims.sub} onClick={()=>run("/api/v1/hr/leave-requests/"+item.id+"/review","POST",{decision:"Rejected",review_note:"Reviewed in HR workspace"},"Leave request rejected.")}>Reject</button></div>:item.reviewer_subject||"—"}</td></tr>)}
        </tbody></table>{!data.leave.length&&<Empty icon={CalendarDays} title="No leave requests" text="Submitted requests will appear here."/>}</div>
      </section>
    </>}

    {name === "Employee assets" && <>
      <section className="people-panel">
        <PanelHeading icon={Laptop} title="Employee assets" subtitle="Issue and return records are part of the offboarding control chain"/>
        {can("hr:employee:read") && <EmployeePicker employees={data.employees} value={selectedEmployeeId} onChange={setSelectedEmployeeId}/>}
        {employee && <div className="people-employee-card"><b>{employee.first_name} {employee.last_name}</b><span>{employee.employee_code || employee.id}</span></div>}
        {employee && can("hr:asset:write") && <form className="people-form" onSubmit={e => submit(e, "/api/v1/hr/employees/" + employee.id + "/assets", "POST", {
          asset_reference: form.asset_reference, asset_type: form.asset_type, issued_on: form.issued_on || today(), condition_on_issue: form.condition_on_issue || null
        }, "Asset issued to employee.")}>
          {field("asset_reference", "Asset reference")}{field("asset_type", "Asset type")}{field("issued_on", "Issue date", "date", false)}{field("condition_on_issue", "Condition on issue", "text", false)}
          <button className="btn btn-primary" disabled={busy}>Issue asset</button>
        </form>}
        <div className="people-record-list">{assets.map(item=><article className="people-record-card" key={item.id}><div><b>{item.asset_reference}</b><span className={statusClass(item.status)}>{item.status}</span></div><small>{item.asset_type} · Issued {dateText(item.issued_on)}</small>{item.status==="Issued"&&can("hr:asset:write")&&<button className="btn btn-quiet" disabled={busy} onClick={()=>run("/api/v1/hr/assets/"+item.id+"/return","POST",{returned_on:today(),condition_on_return:"Returned"},"Asset return recorded.")}>Record return</button>}</article>)}</div>
      </section>
    </>}

    <div className="people-footnote"><ShieldCheck size={14}/> API permissions and organization scope remain authoritative. Employee balances, statutory rules and external identity actions are not inferred.</div>
  </div>;
}

function PanelHeading({ icon: Icon, title, subtitle, count }) {
  return <div className="people-panel-heading"><div className="people-heading-icon"><Icon size={18}/></div><div><h2>{title}</h2><p>{subtitle}</p></div>{count !== undefined && <span className="people-count">{count}</span>}</div>;
}
function EmployeePicker({ employees, value, onChange }) {
  return <label className="people-picker">Employee record<select value={value} onChange={e=>onChange(e.target.value)}><option value="">Select employee…</option>{employees.map(x=><option key={x.id} value={x.id}>{x.first_name} {x.last_name} · {x.employee_code || x.id}</option>)}</select></label>;
}
function Empty({ icon: Icon, title, text }) {
  return <div className="people-empty"><Icon size={22}/><b>{title}</b><span>{text}</span></div>;
}
