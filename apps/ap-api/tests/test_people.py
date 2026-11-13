from datetime import date, timedelta

from asaa_ap.security import Principal, get_principal


def create_employee(client):
    response = client.post("/api/v1/hr/employees", json={
        "employee_code": "E-001", "first_name": "Asha", "last_name": "Rao",
        "work_email": "asha@example.invalid", "employment_type": "Employee",
        "hire_date": "2026-11-01"
    })
    assert response.status_code == 201
    return response.json()


def test_hr_employee_and_effective_dated_employment_history(client):
    employee = create_employee(client)
    record = client.post(
        f"/api/v1/hr/employees/{employee['id']}/employment-records",
        json={
            "department_id": "dept-engineering", "position_title": "Software Engineer",
            "employment_type": "Employee", "status": "Active",
            "effective_from": date.today().isoformat(), "reason": "Initial appointment"
        },
    )
    assert record.status_code == 201
    history = client.get(
        f"/api/v1/hr/employees/{employee['id']}/employment-records"
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["position_title"] == "Software Engineer"
    assert client.get(f"/api/v1/hr/employees/{employee['id']}").json()["status"] == "Active"
    duplicate = client.post(
        f"/api/v1/hr/employees/{employee['id']}/employment-records",
        json={
            "position_title": "Duplicate role", "employment_type": "Employee",
            "status": "Active", "effective_from": date.today().isoformat(),
            "reason": "Must not overlap the current effective record"
        },
    )
    assert duplicate.status_code == 409


def test_onboarding_template_assignment_and_task_completion(client):
    employee = create_employee(client)
    template = client.post("/api/v1/onboarding/templates", json={
        "template_code": "GENERAL-01", "name": "General employee onboarding",
        "tasks": [
            {"title": "Sign employment documents", "description": "Complete required employment paperwork", "owner_role": "HR", "required": True, "sequence": 1},
            {"title": "Prepare workstation", "owner_role": "IT", "required": True, "sequence": 2}
        ]
    })
    assert template.status_code == 201
    listed = client.get("/api/v1/onboarding/templates").json()
    template_view = next(item for item in listed if item["id"] == template.json()["id"])
    assert len(template_view["tasks"]) == 2
    assignment = client.post("/api/v1/onboarding/assignments", json={
        "employee_id": employee["id"], "template_id": template.json()["id"],
        "target_date": "2026-12-10"
    })
    assert assignment.status_code == 201
    assigned = client.get("/api/v1/onboarding/assignments").json()[0]
    assert len(assigned["tasks"]) == 2
    assert assigned["tasks"][0]["description"] == "Complete required employment paperwork"
    for task in assigned["tasks"]:
        updated = client.patch(f"/api/v1/onboarding/tasks/{task['id']}", json={
            "status": "Completed", "evidence_reference": "evidence://onboarding/task",
            "due_date": "2026-12-08"
        })
        assert updated.status_code == 200
        assert updated.json()["due_date"] == "2026-12-08"
        assert updated.json()["evidence_reference"] == "evidence://onboarding/task"
        revised = client.patch("/api/v1/onboarding/tasks/" + task["id"], json={
            "status": "Completed", "due_date": "2026-12-09"
        })
        assert revised.status_code == 200
        assert revised.json()["evidence_reference"] == "evidence://onboarding/task"
    final_assignment = client.get("/api/v1/onboarding/assignments").json()[0]
    assert final_assignment["status"] == "Completed"


def test_compensation_and_payroll_run_foundation(client):
    employee = create_employee(client)
    compensation = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "65000.00", "frequency": "Monthly",
        "effective_from": "2026-12-01"
    })
    assert compensation.status_code == 201
    period = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12", "start_date": "2026-12-01", "end_date": "2026-12-31"
    })
    assert period.status_code == 201
    run = client.post("/api/v1/payroll/runs", json={
        "period_id": period.json()["id"], "run_code": "2026-12-REG-01", "currency": "INR"
    })
    assert run.status_code == 201
    entry = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/entries", json={
        "employee_id": employee["id"], "currency": "INR",
        "gross_amount": "65000.00", "deduction_total": "0.00",
        "net_amount": "65000.00", "breakdown": {"source": "approved payroll input"}
    })
    assert entry.status_code == 201
    assert entry.json()["status"] == "Draft"


def test_salary_data_requires_separate_permission(client):
    employee = create_employee(client)
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "hr-reader", "org-a", frozenset({"hr:employee:read"})
    )
    response = client.get(f"/api/v1/payroll/compensation?employee_id={employee['id']}")
    assert response.status_code == 403


def test_employee_profile_update_and_lifecycle_history(client):
    employee = create_employee(client)
    profile = client.patch(f"/api/v1/hr/employees/{employee['id']}", json={
        "preferred_name": "Ash"
    })
    assert profile.status_code == 200
    assert profile.json()["preferred_name"] == "Ash"

    invalid_transition = client.post(
        "/api/v1/hr/employees/" + employee["id"] + "/lifecycle",
        json={"status": "Suspended", "effective_from": date.today().isoformat(), "reason": "Invalid transition"}
    )
    assert invalid_transition.status_code == 409
    transition = client.post(
        f"/api/v1/hr/employees/{employee['id']}/lifecycle",
        json={
            "status": "Active",
            "effective_from": "2026-11-12",
            "reason": "Start of active engagement"
        },
    )
    assert transition.status_code == 201
    assert transition.json()["status"] == "Active"

    detail = client.get(f"/api/v1/hr/employees/{employee['id']}")
    assert detail.json()["status"] == "Active"
    history = client.get(
        f"/api/v1/hr/employees/{employee['id']}/employment-records"
    )
    assert len(history.json()) == 1
    assert history.json()[0]["reason"] == "Start of active engagement"


def test_payroll_entry_rejects_inconsistent_amounts(client):
    employee = create_employee(client)
    period = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12-VALIDATION",
        "start_date": "2026-12-01",
        "end_date": "2026-12-31"
    })
    assert period.status_code == 201
    run = client.post("/api/v1/payroll/runs", json={
        "period_id": period.json()["id"],
        "run_code": "2026-12-VALIDATION-01",
        "currency": "INR"
    })
    assert run.status_code == 201
    response = client.post(
        f"/api/v1/payroll/runs/{run.json()['id']}/entries",
        json={
            "employee_id": employee["id"],
            "currency": "INR",
            "gross_amount": "50000.00",
            "deduction_total": "5000.00",
            "net_amount": "47000.00",
            "breakdown": {}
        },
    )
    assert response.status_code == 422


def test_optional_only_onboarding_template_completes_assignment(client):
    employee = create_employee(client)
    template = client.post("/api/v1/onboarding/templates", json={
        "template_code": "OPTIONAL-01",
        "name": "Optional welcome resources",
        "tasks": [
            {"title": "Explore team resources", "description": "Optional self-guided reading",
             "owner_role": "Employee", "required": False, "sequence": 1}
        ]
    })
    assert template.status_code == 201
    assignment = client.post("/api/v1/onboarding/assignments", json={
        "employee_id": employee["id"],
        "template_id": template.json()["id"]
    })
    assert assignment.status_code == 201
    assert assignment.json()["status"] == "Completed"
    tasks = client.get("/api/v1/onboarding/assignments").json()[0]["tasks"]
    assert any(task["description"] == "Optional self-guided reading" for task in tasks)
    assert all(task["status"] == "Pending" for task in tasks)


def test_employee_documents_assets_and_offboarding_controls(client):
    employee = create_employee(client)
    document = client.post(f"/api/v1/hr/employees/{employee['id']}/documents", json={
        "document_type": "PolicyAcknowledgement", "title": "Code of conduct acknowledgement",
        "storage_reference": "private-object://hr/employee/document-001",
        "classification": "Restricted", "issued_on": "2026-11-01"
    })
    assert document.status_code == 201
    assert "content" not in document.json()
    documents = client.get(f"/api/v1/hr/employees/{employee['id']}/documents")
    assert documents.status_code == 200
    assert len(documents.json()) == 1
    archived = client.patch("/api/v1/hr/documents/" + document.json()["id"] + "/status", json={"status": "Archived"})
    assert archived.status_code == 200
    assert client.get("/api/v1/hr/employees/" + employee["id"] + "/documents").json() == []

    asset = client.post(f"/api/v1/hr/employees/{employee['id']}/assets", json={
        "asset_reference": "ASSET-LAPTOP-001", "asset_type": "Laptop",
        "issued_on": "2026-11-12", "condition_on_issue": "Good"
    })
    assert asset.status_code == 201
    template = client.post("/api/v1/onboarding/templates", json={
        "template_code": "EXIT-01", "name": "Standard offboarding checklist",
        "workflow_type": "Offboarding",
        "tasks": [{"title": "Complete handover and revoke access", "owner_role": "IT/Manager", "required": True}]
    })
    assert template.status_code == 201
    exit_case = client.post(f"/api/v1/hr/employees/{employee['id']}/exit-cases", json={
        "planned_last_day": date.today().isoformat(), "reason_category": "Voluntary",
        "notes": "Handover and access review to be completed",
        "offboarding_template_id": template.json()["id"]
    })
    assert exit_case.status_code == 201
    assert exit_case.json()["checklist_assignment_id"] is not None
    blocked = client.post(f"/api/v1/hr/exit-cases/{exit_case.json()['id']}/complete")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "offboarding_checklist_incomplete"
    assignments = client.get("/api/v1/onboarding/assignments?employee_id=" + employee["id"]).json()
    exit_task = assignments[0]["tasks"][0]
    completed_task = client.patch("/api/v1/onboarding/tasks/" + exit_task["id"], json={
        "status": "Completed"
    })
    assert completed_task.status_code == 200
    blocked_assets = client.post(f"/api/v1/hr/exit-cases/{exit_case.json()['id']}/complete")
    assert blocked_assets.status_code == 409
    assert blocked_assets.json()["detail"]["code"] == "outstanding_assets"

    returned = client.post(f"/api/v1/hr/assets/{asset.json()['id']}/return", json={
        "returned_on": "2026-11-12", "condition_on_return": "Good"
    })
    assert returned.status_code == 200
    completed = client.post(f"/api/v1/hr/exit-cases/{exit_case.json()['id']}/complete")
    assert completed.status_code == 200
    assert client.get(f"/api/v1/hr/employees/{employee['id']}").json()["status"] == "Inactive"


def test_leave_request_requires_separate_reviewer_and_prevents_overlap(client):
    employee = create_employee(client)
    request = client.post(f"/api/v1/hr/employees/{employee['id']}/leave-requests", json={
        "leave_category": "Personal", "start_date": "2026-11-20",
        "end_date": "2026-11-22", "reason": "Personal commitment"
    })
    assert request.status_code == 201
    overlap = client.post(f"/api/v1/hr/employees/{employee['id']}/leave-requests", json={
        "leave_category": "Other", "start_date": "2026-11-22",
        "end_date": "2026-11-23"
    })
    assert overlap.status_code == 409
    self_review = client.post(f"/api/v1/hr/leave-requests/{request.json()['id']}/review", json={
        "decision": "Approved"
    })
    assert self_review.status_code == 403
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "independent-reviewer", "org-a", frozenset({"hr:leave:review", "hr:leave:read"})
    )
    reviewed = client.post(f"/api/v1/hr/leave-requests/{request.json()['id']}/review", json={
        "decision": "Approved", "review_note": "Reviewed by an authorized reviewer"
    })
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "Approved"


def test_onboarding_template_deactivation_and_task_assignment(client):
    employee = create_employee(client)
    template = client.post("/api/v1/onboarding/templates", json={
        "template_code": "ASSIGN-01", "name": "Assigned onboarding tasks",
        "tasks": [{"title": "Prepare access", "owner_role": "IT", "required": True}]
    })
    assert template.status_code == 201
    assignment = client.post("/api/v1/onboarding/assignments", json={
        "employee_id": employee["id"], "template_id": template.json()["id"]
    })
    assert assignment.status_code == 201
    assert assignment.json()["template_version"] == 1
    task = assignment.json()
    tasks = client.get("/api/v1/onboarding/assignments").json()[0]["tasks"]
    assigned = client.patch(f"/api/v1/onboarding/tasks/{tasks[0]['id']}/assignee", json={
        "assigned_to": "it-owner-01"
    })
    assert assigned.status_code == 200
    assert assigned.json()["assigned_to"] == "it-owner-01"
    revised_template = client.put("/api/v1/onboarding/templates/" + template.json()["id"], json={
        "name": "Assigned onboarding tasks v2", "description": "Updated template",
        "tasks": [{"title": "Prepare revised access", "owner_role": "IT", "required": True}]
    })
    assert revised_template.status_code == 200
    assert revised_template.json()["version"] == 2
    assert assignment.json()["template_version"] == 1
    refreshed_tasks = client.get("/api/v1/onboarding/assignments").json()[0]["tasks"]
    assert refreshed_tasks[0]["title"] == "Prepare access"
    deactivated = client.patch(f"/api/v1/onboarding/templates/{template.json()['id']}/status", json={
        "active": False
    })
    assert deactivated.status_code == 200
    blocked = client.post("/api/v1/onboarding/assignments", json={
        "employee_id": employee["id"], "template_id": template.json()["id"]
    })
    assert blocked.status_code == 404


def test_compensation_requires_independent_approval(client):
    employee = create_employee(client)
    compensation = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "70000.00", "frequency": "Monthly",
        "effective_from": "2026-12-01"
    })
    assert compensation.status_code == 201
    self_approval = client.post(
        f"/api/v1/payroll/compensation/{compensation.json()['id']}/decision",
        json={"decision": "Approved"}
    )
    assert self_approval.status_code == 403
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-reviewer", "org-a", frozenset({"payroll:compensation:approve"})
    )
    approved = client.post(
        f"/api/v1/payroll/compensation/{compensation.json()['id']}/decision",
        json={"decision": "Approved", "approval_note": "Independent approval"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    assert approved.json()["approved_by"] == "payroll-reviewer"
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "tester", "org-a", frozenset({"payroll:compensation:write"})
    )
    next_record = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "75000.00", "frequency": "Monthly",
        "effective_from": "2027-01-01"
    })
    assert next_record.status_code == 201
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-reviewer", "org-a", frozenset({"payroll:compensation:approve", "payroll:compensation:read"})
    )
    next_approved = client.post(
        "/api/v1/payroll/compensation/" + next_record.json()["id"] + "/decision",
        json={"decision": "Approved"}
    )
    assert next_approved.status_code == 200
    records = client.get("/api/v1/payroll/compensation?employee_id=" + employee["id"]).json()
    previous = next(item for item in records if item["id"] == compensation.json()["id"])
    assert previous["effective_to"] == "2026-12-31"


def test_payroll_run_review_summary_and_close_controls(client):
    employee = create_employee(client)
    period = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-11-REVIEW", "start_date": "2026-11-01", "end_date": "2026-11-30"
    })
    assert period.status_code == 201
    run = client.post("/api/v1/payroll/runs", json={
        "period_id": period.json()["id"], "run_code": "2026-11-REVIEW-01", "currency": "INR"
    })
    assert run.status_code == 201
    entry = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/entries", json={
        "employee_id": employee["id"], "currency": "INR",
        "gross_amount": "50000.00", "deduction_total": "5000.00",
        "net_amount": "45000.00", "breakdown": {"source": "approved manual input"}
    })
    assert entry.status_code == 201
    summary = client.get(f"/api/v1/payroll/runs/{run.json()['id']}/summary")
    assert summary.status_code == 200
    assert summary.json()["gross_total"] == "50000.00"
    assert summary.json()["entries_reconciled"] is True
    submitted = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/submit", json={
        "review_note": "Ready for independent review"
    })
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "In Review"
    blocked_edit = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/entries", json={
        "employee_id": employee["id"], "currency": "INR",
        "gross_amount": "100.00", "deduction_total": "0.00", "net_amount": "100.00"
    })
    assert blocked_edit.status_code == 409
    self_approval = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/decision", json={
        "decision": "Approved"
    })
    assert self_approval.status_code == 403
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-approver", "org-a", frozenset({"payroll:run:approve", "payroll:run:close"})
    )
    returned = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/decision", json={
        "decision": "Rejected", "approval_note": "Please correct the entry"
    })
    assert returned.status_code == 200
    assert returned.json()["status"] == "Changes Requested"
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "tester", "org-a", frozenset({"payroll:entry:write", "payroll:run:submit"})
    )
    corrected = client.patch("/api/v1/payroll/entries/" + entry.json()["id"], json={
        "currency": "INR", "gross_amount": "51000.00",
        "deduction_total": "5000.00", "net_amount": "46000.00",
        "breakdown": {"source": "reviewer correction"}
    })
    assert corrected.status_code == 200
    assert corrected.json()["net_amount"] == 46000.0
    resubmitted = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/submit", json={
        "review_note": "Corrected and resubmitted"
    })
    assert resubmitted.status_code == 200
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-approver", "org-a", frozenset({"payroll:run:approve", "payroll:run:close", "payroll:period:close"})
    )
    approved = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/decision", json={
        "decision": "Approved", "approval_note": "Totals reviewed"
    })
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    closed = client.post(f"/api/v1/payroll/runs/{run.json()['id']}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "Closed"
    closed_period = client.post("/api/v1/payroll/periods/" + period.json()["id"] + "/close")
    assert closed_period.status_code == 200
    assert closed_period.json()["status"] == "Closed"

def test_future_dated_employment_change_preserves_current_status_until_effective_date(client):
    employee = create_employee(client)
    initial = client.post(f"/api/v1/hr/employees/{employee['id']}/employment-records", json={
        "position_title": "Analyst",
        "employment_type": "Employee",
        "status": "Active",
        "effective_from": date.today().isoformat(),
        "reason": "Initial appointment",
    })
    assert initial.status_code == 201

    future_date = date.today() + timedelta(days=1)
    scheduled = client.post(
        f"/api/v1/hr/employees/{employee['id']}/employment-records",
        json={
            "position_title": "Senior Analyst",
            "employment_type": "Employee",
            "status": "Active",
            "effective_from": future_date.isoformat(),
            "reason": "Approved promotion effective next day",
        },
    )
    assert scheduled.status_code == 201
    assert scheduled.json()["position_title"] == "Senior Analyst"

    current = client.get(f"/api/v1/hr/employees/{employee['id']}").json()
    assert current["status"] == "Active"
    history = client.get(
        f"/api/v1/hr/employees/{employee['id']}/employment-records"
    ).json()
    assert history[0]["effective_from"] == future_date.isoformat()
    assert history[1]["effective_to"] == (future_date - timedelta(days=1)).isoformat()


def test_payroll_period_rejects_duplicate_codes_and_overlapping_dates_with_org_scope(client):
    first = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12",
        "start_date": "2026-12-01",
        "end_date": "2026-12-31",
    })
    assert first.status_code == 201

    duplicate_code = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12",
        "start_date": "2027-01-01",
        "end_date": "2027-01-31",
    })
    assert duplicate_code.status_code == 409
    assert duplicate_code.json()["detail"]["code"] == "payroll_period_code_exists"

    overlap = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12-OVERLAP",
        "start_date": "2026-12-15",
        "end_date": "2027-01-15",
    })
    assert overlap.status_code == 409
    assert overlap.json()["detail"]["code"] == "payroll_period_overlap"
    assert overlap.json()["detail"]["conflicting_period_code"] == "2026-12"

    adjacent = client.post("/api/v1/payroll/periods", json={
        "period_code": "2027-01",
        "start_date": "2027-01-01",
        "end_date": "2027-01-31",
    })
    assert adjacent.status_code == 201

    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-admin-b", "org-b", frozenset({"payroll:period:write"})
    )
    other_org = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12",
        "start_date": "2026-12-01",
        "end_date": "2026-12-31",
    })
    assert other_org.status_code == 201

    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-admin-a", "org-a", frozenset({"payroll:period:write"})
    )
    cross_org_overlap = client.post("/api/v1/payroll/periods", json={
        "period_code": "2026-12-ALT",
        "start_date": "2026-12-10",
        "end_date": "2026-12-20",
    })
    assert cross_org_overlap.status_code == 409


def test_compensation_timeline_overlap_and_independent_approval(client):
    employee = create_employee(client)
    proposal = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "65000.00", "frequency": "Monthly",
        "effective_from": "2026-12-01", "effective_to": "2026-12-31"
    })
    assert proposal.status_code == 201
    assert proposal.json()["status"] == "Pending Approval"

    overlapping = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "70000.00", "frequency": "Monthly", "effective_from": "2026-12-15"
    })
    assert overlapping.status_code == 409
    assert overlapping.json()["detail"]["code"] == "compensation_effective_period_overlap"

    adjacent = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "70000.00", "frequency": "Monthly", "effective_from": "2027-01-01"
    })
    assert adjacent.status_code == 201

    self_approval = client.post("/api/v1/payroll/compensation/" + proposal.json()["id"] + "/decision", json={
        "decision": "Approved", "approval_note": "Self approval must fail"
    })
    assert self_approval.status_code == 403
    assert self_approval.json()["detail"]["code"] == "maker_cannot_approve_own_compensation"

    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-approver", "org-a", frozenset({"payroll:compensation:approve"})
    )
    approved = client.post("/api/v1/payroll/compensation/" + proposal.json()["id"] + "/decision", json={
        "decision": "Approved", "approval_note": "Independently reviewed"
    })
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    assert approved.json()["approved_by"] == "payroll-approver"
    assert approved.json()["approved_at"] is not None

    repeated = client.post("/api/v1/payroll/compensation/" + proposal.json()["id"] + "/decision", json={
        "decision": "Rejected", "approval_note": "Cannot change decision"
    })
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "compensation_not_pending"


def test_rejected_compensation_proposal_does_not_block_future_timeline(client):
    employee = create_employee(client)
    proposal = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "65000.00", "frequency": "Monthly", "effective_from": "2026-12-01"
    })
    assert proposal.status_code == 201

    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-approver", "org-a", frozenset({"payroll:compensation:approve"})
    )
    rejected = client.post("/api/v1/payroll/compensation/" + proposal.json()["id"] + "/decision", json={
        "decision": "Rejected", "approval_note": "Incorrect proposal"
    })
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"

    client.app.dependency_overrides[get_principal] = lambda: Principal(
        "payroll-maker", "org-a", frozenset({"payroll:compensation:write"})
    )
    replacement = client.post("/api/v1/payroll/compensation", json={
        "employee_id": employee["id"], "currency": "INR", "pay_basis": "Fixed",
        "gross_amount": "66000.00", "frequency": "Monthly", "effective_from": "2026-12-01"
    })
    assert replacement.status_code == 201
