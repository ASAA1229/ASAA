"""Organization unit hierarchy integrity: no self-parent, no cycles, valid parent types, same-organization parents."""
from asaa_ap.security import Principal, get_principal

ADMIN = {"organization:structure:read", "organization:structure:write", "organization:structure:approve", "audit:read"}
BASE = "/api/v1/administration/units"


def as_p(client, org="org-a", perms=ADMIN):
    client.app.dependency_overrides[get_principal] = lambda: Principal("admin", org, frozenset(perms))


def unit(client, code, unit_type, parent=None):
    body = {"unit_type": unit_type, "unit_code": code, "name": code.title()}
    if parent:
        body["parent_id"] = parent
    response = client.post(BASE, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def move(client, row, parent_id, **extra):
    return client.patch(f"{BASE}/{row['id']}", json={"expected_version": row["version"], "parent_id": parent_id, **extra})


def chain(client):
    entity = unit(client, "entity", "Legal Entity")
    division = unit(client, "division", "Division", entity["id"])
    department = unit(client, "department", "Department", division["id"])
    team = unit(client, "team", "Team", department["id"])
    return entity, division, department, team


def test_self_parent_is_rejected_on_update(client):
    as_p(client)
    department = unit(client, "dept", "Department")
    response = move(client, department, department["id"])
    assert response.status_code == 422 and response.json()["detail"]["code"] == "organization_unit_self_parent"
    assert client.get(BASE).json()[0]["parent_id"] is None


def test_direct_and_indirect_cycles_are_rejected(client):
    as_p(client)
    entity, division, department, team = chain(client)
    for target in (division, department, team):
        response = move(client, entity, target["id"])
        assert response.status_code == 422, target["unit_code"]
        assert response.json()["detail"]["code"] == "organization_unit_parent_cycle"
    # A move that is not a cycle still works and a rejected move changed nothing.
    parents = {u["unit_code"]: u["parent_id"] for u in client.get(BASE).json()}
    assert parents["entity"] is None and parents["division"] == entity["id"]


def test_valid_reparenting_succeeds_and_is_audited(client):
    as_p(client)
    entity, division, department, team = chain(client)
    other = unit(client, "dept2", "Department", division["id"])
    response = move(client, team, other["id"])
    assert response.status_code == 200 and response.json()["parent_id"] == other["id"] and response.json()["version"] == 2
    audit = client.get("/api/v1/ap/audit-events", params={"action": "organization_unit.updated"}).json()
    assert audit and "parent_id" in audit[0]["details"]["changed_fields"]


def test_moving_to_the_top_level_with_explicit_null_is_allowed(client):
    as_p(client)
    entity, division, *_ = chain(client)
    response = move(client, division, None)
    assert response.status_code == 200 and response.json()["parent_id"] is None


def test_invalid_parent_type_unknown_parent_and_other_org_parent_are_rejected(client):
    as_p(client)
    entity, division, department, team = chain(client)
    bad_type = move(client, entity, team["id"])  # a Legal Entity cannot sit under a Team (also a cycle: cycle is reported first)
    assert bad_type.status_code == 422
    location = unit(client, "loc", "Location")
    under_location = move(client, team, location["id"])
    assert under_location.status_code == 422 and under_location.json()["detail"]["code"] == "invalid_organization_parent_type"
    assert move(client, team, "00000000-0000-0000-0000-000000000000").status_code == 404
    as_p(client, org="org-b")
    foreign = unit(client, "b-dept", "Department")
    as_p(client, org="org-a")
    assert move(client, team, foreign["id"]).status_code == 404


def test_create_still_validates_parent_existence_type_and_organization(client):
    as_p(client)
    entity = unit(client, "entity", "Legal Entity")
    team = unit(client, "team", "Team", unit(client, "dept", "Department", entity["id"])["id"])
    for code, kind, parent, status in (("x1", "Division", team["id"], 422), ("x2", "Team", "11111111-1111-1111-1111-111111111111", 404)):
        response = client.post(BASE, json={"unit_type": kind, "unit_code": code, "name": code.title(), "parent_id": parent})
        assert response.status_code == status, code
    assert client.post(BASE, json={"unit_type": "Team", "unit_code": "t1", "name": "T1", "parent_id": entity["id"]}).status_code == 422


def test_updates_without_parent_change_do_not_run_hierarchy_checks(client):
    as_p(client)
    entity, division, *_ = chain(client)
    response = client.patch(f"{BASE}/{division['id']}", json={"expected_version": division["version"], "name": "Renamed Division"})
    assert response.status_code == 200 and response.json()["parent_id"] == entity["id"]


def test_parent_change_requires_structure_write_permission(client):
    as_p(client)
    entity, division, department, team = chain(client)
    as_p(client, perms={"organization:structure:read"})
    assert move(client, team, division["id"]).status_code == 403
