def create_domain(client, code="people"):
    return client.post("/api/v1/master-data/domains", json={
        "domain_code": code,
        "name": f"{code.title()} master data",
        "authoritative_source": "ASAA HR",
        "owner_subject": "owner-1",
        "steward_subject": "steward-1",
    })


def create_record(client, domain_id, record_id, source_id, fingerprint=None):
    payload = {
        "record_type": "employee",
        "record_id": record_id,
        "source_system": "asaa-hr",
        "source_record_id": source_id,
    }
    if fingerprint:
        payload["match_key_fingerprint"] = fingerprint
    return client.post(f"/api/v1/master-data/domains/{domain_id}/records", json=payload)


def test_master_data_domain_create_list_and_audit(client):
    response = create_domain(client)
    assert response.status_code == 201
    domain = response.json()
    assert domain["status"] == "Active"
    assert domain["version"] == 1
    listed = client.get("/api/v1/master-data/domains")
    assert listed.status_code == 200
    assert listed.json()[0]["domain_code"] == "people"
    events = client.get("/api/v1/ap/audit-events").json()
    assert any(event["action"] == "master_data_domain.created" for event in events)


def test_master_data_domain_duplicate_and_optimistic_update(client):
    domain = create_domain(client).json()
    assert create_domain(client).status_code == 409
    updated = client.patch(f"/api/v1/master-data/domains/{domain['id']}", json={
        "expected_version": 1, "steward_subject": "steward-2"
    })
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    stale = client.patch(f"/api/v1/master-data/domains/{domain['id']}", json={
        "expected_version": 1, "name": "Stale update"
    })
    assert stale.status_code == 409


def test_master_data_record_registration_and_duplicate_flagging(client):
    domain = create_domain(client).json()
    first = create_record(client, domain["id"], "emp-1", "source-1", "a" * 64)
    assert first.status_code == 201
    assert first.json()["status"] == "Active"
    second = create_record(client, domain["id"], "emp-2", "source-2", "a" * 64)
    assert second.status_code == 201
    assert second.json()["status"] == "Duplicate Review"
    assert len(second.json()["duplicate_candidates"]) == 1
    assert create_record(client, domain["id"], "emp-1", "source-3").status_code == 409
    assert create_record(client, domain["id"], "emp-3", "source-1").status_code == 409


def test_master_data_supersession_is_non_destructive_and_scoped(client):
    domain = create_domain(client).json()
    first = create_record(client, domain["id"], "emp-1", "source-1").json()
    second = create_record(client, domain["id"], "emp-2", "source-2", "b" * 64).json()
    response = client.post(f"/api/v1/master-data/records/{second['id']}/supersede", json={
        "canonical_record_id": first["id"], "reason": "Verified duplicate by steward"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "Superseded"
    assert response.json()["canonical_record_id"] == first["id"]
    assert client.get(f"/api/v1/master-data/domains/{domain['id']}/records?status=Superseded").json()[0]["id"] == second["id"]
    assert client.post(f"/api/v1/master-data/records/{first['id']}/supersede", json={
        "canonical_record_id": second["id"], "reason": "Cycle attempt"
    }).status_code == 404


def test_master_data_is_organization_scoped(client):
    domain = create_domain(client).json()
    from asaa_ap.security import get_principal, Principal
    client.app.dependency_overrides[get_principal] = lambda: Principal("other", "org-b", frozenset({"masterdata:domain:read", "masterdata:record:read"}))
    assert client.get(f"/api/v1/master-data/domains/{domain['id']}/records").status_code == 404
    assert client.get("/api/v1/master-data/domains").json() == []


def test_master_data_permissions_are_separate(client):
    from asaa_ap.security import get_principal, Principal
    client.app.dependency_overrides[get_principal] = lambda: Principal("reader", "org-a", frozenset({"masterdata:domain:read"}))
    assert client.get("/api/v1/master-data/domains").status_code == 200
    assert client.post("/api/v1/master-data/domains", json={
        "domain_code": "assets", "name": "Assets", "authoritative_source": "ASAA",
        "owner_subject": "owner", "steward_subject": "steward",
    }).status_code == 403
