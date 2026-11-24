from datetime import datetime, timedelta, timezone

from asaa_ap.security import Principal, get_principal


ALL_GOVERNANCE = {
    "governance:delegation:read", "governance:delegation:create",
    "governance:delegation:approve", "governance:delegation:reject", "governance:delegation:revoke",
    "governance:decision:read", "governance:decision:create",
    "governance:decision:approve", "governance:decision:reject",
}


def as_subject(client, subject, permissions=None, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(
        subject, org, frozenset(ALL_GOVERNANCE if permissions is None else permissions)
    )


def delegation_payload():
    now = datetime.now(timezone.utc)
    return {
        "delegator_subject": "delegator-1",
        "delegate_subject": "delegate-1",
        "scope_code": "finance.ap",
        "action_code": "invoice.approve",
        "effective_from": now.isoformat(),
        "effective_to": (now + timedelta(days=2)).isoformat(),
        "reason": "Temporary coverage during planned absence",
        "evidence_reference": "policy-record:123",
    }


def decision_payload():
    return {
        "decision_type": "operational",
        "title": "Approve initial service operating model",
        "scope_reference": "operations/service-model/v1",
        "rationale": "Selected after review of the documented options and constraints.",
        "decision_maker_subject": "maker-1",
        "evidence_reference": "meeting-record:2026-11-12",
    }


def test_delegation_requires_independent_approval_and_can_be_revoked(client):
    created = client.post("/api/v1/governance/delegations", json=delegation_payload())
    assert created.status_code == 201
    row = created.json()
    assert row["status"] == "Pending Approval"
    assert row["effective_now"] is False

    # The creator cannot approve their own request.
    assert client.post(
        f"/api/v1/governance/delegations/{row['id']}/approve",
        json={"expected_version": 1},
    ).status_code == 403

    as_subject(client, "independent-reviewer")
    approved = client.post(
        f"/api/v1/governance/delegations/{row['id']}/approve",
        json={"expected_version": 1, "reason": "Authority independently verified"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    assert approved.json()["effective_now"] is True
    assert approved.json()["reviewed_by"] == "independent-reviewer"

    revoked = client.post(
        f"/api/v1/governance/delegations/{row['id']}/revoke",
        json={"expected_version": 2, "reason": "Temporary coverage ended"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "Revoked"
    assert revoked.json()["effective_now"] is False


def test_delegation_reject_requires_reason_and_reviewer_separation(client):
    row = client.post("/api/v1/governance/delegations", json=delegation_payload()).json()
    as_subject(client, "independent-reviewer")
    missing_reason = client.post(
        f"/api/v1/governance/delegations/{row['id']}/reject",
        json={"expected_version": 1},
    )
    assert missing_reason.status_code == 422
    rejected = client.post(
        f"/api/v1/governance/delegations/{row['id']}/reject",
        json={"expected_version": 1, "reason": "Scope is not sufficiently defined"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"


def test_delegation_validation_and_version_conflict(client):
    payload = delegation_payload()
    payload["delegate_subject"] = payload["delegator_subject"]
    assert client.post("/api/v1/governance/delegations", json=payload).status_code == 422
    payload = delegation_payload()
    payload["effective_to"] = payload["effective_from"]
    assert client.post("/api/v1/governance/delegations", json=payload).status_code == 422

    row = client.post("/api/v1/governance/delegations", json=delegation_payload()).json()
    as_subject(client, "independent-reviewer")
    stale = client.post(
        f"/api/v1/governance/delegations/{row['id']}/approve",
        json={"expected_version": 7},
    )
    assert stale.status_code == 409


def test_decision_requires_named_decision_maker_and_independent_proposal(client):
    row = client.post("/api/v1/governance/decisions", json=decision_payload())
    assert row.status_code == 201
    decision = row.json()
    assert decision["status"] == "Proposed"
    assert decision["created_by"] == "tester"

    as_subject(client, "another-reviewer")
    wrong_maker = client.post(
        f"/api/v1/governance/decisions/{decision['id']}/approve",
        json={"expected_version": 1},
    )
    assert wrong_maker.status_code == 403

    as_subject(client, "maker-1")
    approved = client.post(
        f"/api/v1/governance/decisions/{decision['id']}/approve",
        json={"expected_version": 1, "reason": "Decision confirmed"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    assert approved.json()["reviewed_by"] == "maker-1"


def test_decision_rejection_is_recorded_with_reason(client):
    row = client.post("/api/v1/governance/decisions", json=decision_payload()).json()
    as_subject(client, "maker-1")
    rejected = client.post(
        f"/api/v1/governance/decisions/{row['id']}/reject",
        json={"expected_version": 1, "reason": "Evidence is incomplete"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"
    assert rejected.json()["review_reason"] == "Evidence is incomplete"


def test_governance_records_are_organization_scoped_and_permissions_separate(client):
    row = client.post("/api/v1/governance/decisions", json=decision_payload()).json()
    as_subject(client, "reader", {"governance:decision:read"})
    assert client.get("/api/v1/governance/decisions").status_code == 200
    assert client.post("/api/v1/governance/decisions", json=decision_payload()).status_code == 403
    as_subject(client, "other-org", ALL_GOVERNANCE, org="org-b")
    assert client.get("/api/v1/governance/decisions").json() == []
    assert client.get("/api/v1/governance/delegations").json() == []


def test_expire_due_persists_lapsed_delegations_audited_and_org_scoped(client):
    from sqlalchemy import select
    from asaa_ap.models import AuditEvent
    from asaa_governance.authority import AuthorityDelegation
    from tests.integration_support import db_of

    row = client.post("/api/v1/governance/delegations", json=delegation_payload()).json()
    as_subject(client, "independent-reviewer")
    assert client.post(f"/api/v1/governance/delegations/{row['id']}/approve", json={"expected_version": 1, "reason": "Verified authority"}).status_code == 200
    assert client.post("/api/v1/governance/delegations/expire-due").json()["expired"] == 0  # still inside its window
    db = db_of(client)
    record = db.get(AuthorityDelegation, row["id"])
    record.effective_to = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    as_subject(client, "other-org-admin", org="org-b")
    assert client.post("/api/v1/governance/delegations/expire-due").json()["expired"] == 0  # another organization cannot expire it
    as_subject(client, "independent-reviewer", permissions={"governance:delegation:read"})
    assert client.post("/api/v1/governance/delegations/expire-due").status_code == 403
    as_subject(client, "independent-reviewer")
    assert client.post("/api/v1/governance/delegations/expire-due").json()["ids"] == [row["id"]]
    listed = client.get("/api/v1/governance/delegations", params={"status": "Expired"}).json()
    assert [r["id"] for r in listed] == [row["id"]] and listed[0]["effective_now"] is False
    assert db_of(client).scalar(select(AuditEvent).where(AuditEvent.action == "authority_delegation.expired")) is not None
