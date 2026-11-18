"""New employment records must reference a real organization unit of the same organization; legacy values stay readable."""
from datetime import date, timedelta

from asaa_ap.database import get_db
from asaa_governance.administration import OrganizationUnit
from asaa_people.models import EmploymentRecord
from asaa_ap.security import Principal, get_principal

from tests.test_people import create_employee, make_unit  # noqa: E402

BASE = "/api/v1/hr/employees/{}/employment-records"


def session_of(client):
    return next(client.app.dependency_overrides[get_db]())


def record(client, employee_id, department_id, day=0, **extra):
    body = {"position_title": "Engineer", "employment_type": "Employee", "status": "Active",
            "effective_from": (date.today() + timedelta(days=day)).isoformat(), **extra}
    if department_id is not None:
        body["department_id"] = department_id
    return client.post(BASE.format(employee_id), json=body)


def test_existing_unit_of_the_same_org_is_accepted(client):
    employee = create_employee(client)
    response = record(client, employee["id"], make_unit(client))
    assert response.status_code == 201


def test_missing_free_text_other_org_and_rejected_units_are_refused(client):
    employee = create_employee(client)
    for index, bad in enumerate(("dept-engineering", "00000000-0000-0000-0000-000000000000", "")):
        response = record(client, employee["id"], bad, day=index)
        assert response.status_code == 422, bad
        assert response.json()["detail"]["code"] == "employment_department_not_found"
    foreign = make_unit(client, code="other-dept", org="org-b")
    rejected = make_unit(client, code="rejected-dept", status="Rejected")
    for index, bad in enumerate((foreign, rejected), start=10):
        response = record(client, employee["id"], bad, day=index)
        assert response.status_code == 422 and response.json()["detail"]["code"] == "employment_department_not_found"
    assert client.get(BASE.format(employee["id"])).json() == []


def test_only_active_units_are_accepted_and_department_stays_optional(client):
    employee = create_employee(client)
    proposed = record(client, employee["id"], make_unit(client, code="prop", status="Proposed"))
    assert proposed.status_code == 422 and proposed.json()["detail"]["code"] == "employment_department_not_found"
    assert record(client, employee["id"], make_unit(client, code="act", status="Active"), day=1).status_code == 201
    assert record(client, employee["id"], None, day=5).status_code == 201


def test_refusal_does_not_leak_whether_a_unit_exists_in_another_org(client):
    employee = create_employee(client)
    foreign = make_unit(client, code="secret-unit", org="org-b")
    unknown = record(client, employee["id"], "11111111-1111-1111-1111-111111111111").json()
    other = record(client, employee["id"], foreign, day=1).json()
    assert unknown == other


def test_legacy_free_text_values_remain_readable_and_carry_over_on_lifecycle_actions(client):
    employee = create_employee(client)
    session = session_of(client)
    session.add(EmploymentRecord(organization_id="org-a", employee_id=employee["id"], department_id="legacy-dept-name",
                                 position_title="Legacy", employment_type="Employee", status="Active",
                                 effective_from=date.today() - timedelta(days=30), created_by="import"))
    session.commit()
    history = client.get(BASE.format(employee["id"])).json()
    assert [r["department_id"] for r in history] == ["legacy-dept-name"]
    # A new write must carry a valid id; the legacy row itself is untouched.
    assert record(client, employee["id"], "legacy-dept-name").status_code == 422
    assert record(client, employee["id"], make_unit(client)).status_code == 201
    legacy = session.query(EmploymentRecord).filter_by(department_id="legacy-dept-name").one()
    assert legacy.department_id == "legacy-dept-name"


def test_validation_uses_the_callers_organization(client):
    unit_a = make_unit(client, code="same-code", org="org-a")
    client.app.dependency_overrides[get_principal] = lambda: Principal("hr-b", "org-b", frozenset({"hr:employee:write", "hr:employment:write", "hr:employee:read"}))
    employee_b = create_employee(client)
    assert record(client, employee_b["id"], unit_a).status_code == 422
    unit_b = make_unit(client, code="b-unit", org="org-b")
    assert record(client, employee_b["id"], unit_b).status_code == 201
    assert session_of(client).query(OrganizationUnit).count() == 2
