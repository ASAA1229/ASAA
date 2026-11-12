from asaa_ap.security import Principal, get_principal


def create_employee(client):
    response = client.post("/api/v1/hr/employees", json={
        "employee_code": "E-001", "first_name": "Asha", "last_name": "Rao",
        "work_email": "asha@example.invalid", "employment_type": "Employee",
        "hire_date": "2026-12-01"
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
            "effective_from": "2026-12-01", "reason": "Initial appointment"
        },
    )
    assert record.status_code == 201
    history = client.get(
        f"/api/v1/hr/employees/{employee['id']}/employment-records"
    )
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["position_title"] == "Software Engineer"


def test_onboarding_template_assignment_and_task_completion(client):
    employee = create_employee(client)
    template = client.post("/api/v1/onboarding/templates", json={
        "template_code": "GENERAL-01", "name": "General employee onboarding",
        "tasks": [
            {"title": "Sign employment documents", "owner_role": "HR", "required": True, "sequence": 1},
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
    for task in assigned["tasks"]:
        updated = client.patch(f"/api/v1/onboarding/tasks/{task['id']}", json={
            "status": "Completed", "evidence_reference": "evidence://onboarding/task"
        })
        assert updated.status_code == 200
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
