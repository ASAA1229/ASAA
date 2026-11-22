"""One-time adoption of pre-existing Keycloak accounts: explicit, audited, maker-checker, never automatic (MOCK Keycloak)."""
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from asaa_ap.models import AuditEvent
from asaa_ap.security import Principal, get_principal
from asaa_identity import service
from asaa_identity.api import get_identity_provider
from asaa_identity.keycloak import KeycloakClient, KeycloakIdentityProvider
from asaa_identity.memory import InMemoryIdentityProvider
from asaa_identity.models import IdentityAdoptionRequest, IdentitySyncJob
from asaa_identity.provider import TransientProviderError
from tests.fake_keycloak import FakeKeycloak
from tests.test_identity_sync import db, employee, link  # noqa: F401  (db is a fixture)

SECRET = "test-client-secret"
BASE = "/api/v1/identity-sync/adoptions"
ROOT = Path(__file__).resolve().parents[1]
REQUESTER = {"identity:adoption:request", "identity:adoption:read", "identity:link:write", "hr:employee:write", "hr:employee:read",
             "identity:sync:read", "identity:sync:run"}
APPROVER = {"identity:adoption:approve", "identity:adoption:read", "identity:sync:read"}


def as_p(client, subject, perms, org="org-a"):
    client.app.dependency_overrides[get_principal] = lambda: Principal(subject, org, frozenset(perms))


@pytest.fixture
def kc(client):
    fake = FakeKeycloak(secret=SECRET)
    provider = KeycloakIdentityProvider(KeycloakClient("http://127.0.0.1:8280", "asaa", "c", SECRET, transport=fake, sleep=lambda s: None), create_groups=True)
    client.app.dependency_overrides[get_identity_provider] = lambda: provider
    fake.provider = provider
    yield fake
    client.app.dependency_overrides.pop(get_identity_provider, None)


def manual_account(kc, username="asha.rao", email="asha@example.invalid", attributes=None, enabled=True):
    kc.users["m1"] = {"id": "m1", "username": username, "email": email, "enabled": enabled, "attributes": attributes or {}}
    kc.memberships["m1"] = set()
    return kc.users["m1"]


def linked_employee(client, code="E-100", subject="sub-asha"):
    as_p(client, "requester", REQUESTER)
    emp = employee(client, "Asha", "Rao", code)
    link(client, emp, subject)
    return emp


def request_adoption(client, emp, username="asha.rao"):
    as_p(client, "requester", REQUESTER)
    return client.post(BASE, json={"employee_id": emp["id"], "provider_username": username, "reason": "Account created by hand before ASAA"})


def review(client, adoption_id, decision="Approve", who="approver", perms=APPROVER):
    as_p(client, who, perms)
    return client.post(f"{BASE}/{adoption_id}/review", json={"decision": decision, "reason": "Checked with the account owner"})


def audits(db, prefix="identity_adoption"):
    return [a for a in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)) if a.action.startswith(prefix)]


def test_a_request_alone_changes_nothing_in_the_provider(client, kc, db):
    emp = linked_employee(client)
    account = manual_account(kc, attributes={"asaa_employee_reference": ["E-100"]})
    before = dict(account)
    response = request_adoption(client, emp)
    assert response.status_code == 201 and response.json()["status"] == "Pending" and response.json()["subject"] == "sub-asha"
    assert kc.users["m1"] == before and not [r for r in kc.requests if r["method"] in {"PUT", "POST"}]
    assert [a.action for a in audits(db)] == ["identity_adoption.requested"]


def test_the_requester_cannot_approve_their_own_request(client, kc):
    emp = linked_employee(client)
    manual_account(kc, attributes={"asaa_employee_reference": ["E-100"]})
    adoption = request_adoption(client, emp).json()
    both = REQUESTER | APPROVER
    refused = review(client, adoption["id"], who="requester", perms=both)
    assert refused.status_code == 403 and refused.json()["detail"]["code"] == "adoption_self_approval_forbidden"
    assert "asaa_managed" not in kc.users["m1"]["attributes"]


def test_a_second_person_approves_and_the_account_becomes_asaa_managed(client, kc, db):
    emp = linked_employee(client)
    manual_account(kc, attributes={"asaa_employee_reference": ["E-100"], "department": ["finance"]})
    adoption = request_adoption(client, emp).json()
    done = review(client, adoption["id"])
    assert done.status_code == 200 and done.json()["status"] == "Approved" and done.json()["reviewed_by"] == "approver"
    attributes = kc.users["m1"]["attributes"]
    assert attributes["asaa_managed"] == ["true"] and attributes["asaa_subject"] == ["sub-asha"]
    assert attributes["asaa_employee_reference"] == ["E-100"] and attributes["department"] == ["finance"]
    assert kc.users["m1"]["enabled"] is True and kc.users["m1"]["email"] == "asha@example.invalid"  # nothing else touched
    actions = [a.action for a in audits(db)]
    assert actions == ["identity_adoption.requested", "identity_adoption.approved"]
    assert audits(db)[1].details["provider_id"] == "m1" and audits(db)[1].details["requested_by"] == "requester"
    assert kc.provider.drain_audit() == [{"subject": "sub-asha", "provider_id": "m1", "action": "adopted"}]
    assert db.scalars(select(IdentitySyncJob).where(IdentitySyncJob.reason == "adoption")).one().operation == "mover"
    assert review(client, adoption["id"]).status_code == 409  # a decided request cannot be reviewed again


def test_adoption_unblocks_a_joiner_that_was_refused_because_the_account_was_not_ours(client, kc, db):
    manual_account(kc, attributes={"asaa_employee_reference": ["E-100"]})
    emp = linked_employee(client)  # linking queues a joiner job
    first = service.process_due(db, kc.provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert first["dead_lettered"] == 1 and "asaa_managed" not in kc.users["m1"]["attributes"]  # never adopted automatically
    adoption = request_adoption(client, emp).json()
    assert review(client, adoption["id"]).status_code == 200
    as_p(client, "requester", REQUESTER)
    dead = client.get("/api/v1/identity-sync/jobs?status=DeadLetter").json()
    assert dead and client.post(f"/api/v1/identity-sync/jobs/{dead[0]['id']}/retry").status_code == 200
    done = service.process_due(db, kc.provider, "org-a", now=datetime.now(timezone.utc) + timedelta(days=1))
    assert done["succeeded"] >= 1 and "employees" in {kc.groups[g]["name"] for g in kc.memberships["m1"]}


def test_email_is_the_proof_when_the_account_has_no_employee_reference(client, kc):
    emp = linked_employee(client)
    manual_account(kc, email="ASHA@example.invalid")
    adoption = request_adoption(client, emp).json()
    assert review(client, adoption["id"]).status_code == 200 and kc.users["m1"]["attributes"]["asaa_managed"] == ["true"]


@pytest.mark.parametrize("account", [
    {"attributes": {"asaa_employee_reference": ["E-999"]}},                         # belongs to another employee
    {"email": "someone.else@example.invalid"},                                       # no reference, email differs
    {"attributes": {"asaa_managed": ["true"], "asaa_subject": ["sub-other"]}},      # already ASAA's, for someone else
    {"attributes": {"asaa_employee_reference": ["E-100"], "asaa_subject": ["x"]}},  # carries an ASAA subject already
])
def test_an_account_that_does_not_match_is_refused_and_left_untouched(client, kc, db, account):
    emp = linked_employee(client)
    manual_account(kc, **account)
    before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in kc.users["m1"].items()}
    adoption = request_adoption(client, emp).json()
    refused = review(client, adoption["id"])
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "adoption_refused"
    assert kc.users["m1"] == before and not [r for r in kc.requests if r["method"] == "PUT"]
    stored = db.scalars(select(IdentityAdoptionRequest)).one()
    assert stored.status == "Failed" and stored.result and "identity_adoption.failed" in [a.action for a in audits(db)]


def test_an_unknown_username_is_refused(client, kc):
    emp = linked_employee(client)
    adoption = request_adoption(client, emp, "does.not.exist").json()
    assert review(client, adoption["id"]).status_code == 422


def test_rejecting_never_calls_the_provider(client, kc, db):
    emp = linked_employee(client)
    manual_account(kc, attributes={"asaa_employee_reference": ["E-100"]})
    adoption = request_adoption(client, emp).json()
    kc.requests.clear()
    rejected = review(client, adoption["id"], "Reject")
    assert rejected.status_code == 200 and rejected.json()["status"] == "Rejected" and kc.requests == []
    assert audits(db)[-1].action == "identity_adoption.rejected"
    assert request_adoption(client, emp).status_code == 201  # a new request may follow a rejected one


def test_a_provider_outage_keeps_the_request_pending(client, kc, db):
    emp = linked_employee(client)
    manual_account(kc, attributes={"asaa_employee_reference": ["E-100"]})
    adoption = request_adoption(client, emp).json()

    class Down(KeycloakIdentityProvider):
        def adopt_account(self, *args, **kwargs):
            raise TransientProviderError("Keycloak unavailable")

    client.app.dependency_overrides[get_identity_provider] = lambda: Down(kc.provider.client)
    response = review(client, adoption["id"])
    assert response.status_code == 503
    assert db.scalars(select(IdentityAdoptionRequest)).one().status == "Pending"


def test_providers_that_cannot_prove_ownership_refuse_to_adopt(client, db):
    client.app.dependency_overrides[get_identity_provider] = lambda: InMemoryIdentityProvider()
    emp = linked_employee(client)
    adoption = request_adoption(client, emp).json()
    refused = review(client, adoption["id"])
    assert refused.status_code == 422 and "does not support adopting" in refused.json()["detail"]["message"]
    client.app.dependency_overrides.pop(get_identity_provider, None)


def test_permissions_duplicates_unlinked_employees_and_organization_scoping(client, kc):
    emp = linked_employee(client)
    manual_account(kc, attributes={"asaa_employee_reference": ["E-100"]})
    as_p(client, "nobody", set())
    assert client.post(BASE, json={"employee_id": emp["id"], "provider_username": "asha.rao", "reason": "no permission"}).status_code == 403
    assert client.get(BASE).status_code == 403
    adoption = request_adoption(client, emp).json()
    assert request_adoption(client, emp).status_code == 409  # one pending request per employee
    assert review(client, adoption["id"], perms={"identity:adoption:read"}).status_code == 403  # approving needs its own permission
    assert review(client, adoption["id"], perms=REQUESTER).status_code == 403
    other = review(client, adoption["id"], who="outsider", perms=APPROVER)
    assert other.status_code == 200
    as_p(client, "outsider", APPROVER, org="org-b")
    assert client.get(BASE).json() == []
    assert client.post(f"{BASE}/{adoption['id']}/review", json={"decision": "Reject", "reason": "other org"}).status_code == 404
    as_p(client, "requester", REQUESTER)
    unlinked = employee(client, "Un", "Linked", "E-200")
    assert client.post(BASE, json={"employee_id": unlinked["id"], "provider_username": "x", "reason": "not linked yet"}).status_code == 404


@pytest.mark.parametrize("bad", [{"provider_username": "with space"}, {"provider_username": "a/b"}, {"provider_username": "a?b"}, {"provider_username": ""},
                                 {"reason": "x"}, {"extra": "field"}])
def test_invalid_requests_are_rejected(client, kc, bad):
    emp = linked_employee(client)
    body = {"employee_id": emp["id"], "provider_username": "asha.rao", "reason": "A valid reason", **bad}
    assert client.post(BASE, json=body).status_code == 422


def test_migration_0022_upgrades_and_downgrades(tmp_path):
    db_file = tmp_path / "adoption.db"
    env = {**os.environ, "ASAA_AP_DATABASE_URL": f"sqlite:///{db_file}"}

    def alembic(*args):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr[-1500:]

    def tables():
        con = sqlite3.connect(db_file)
        try:
            return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()

    alembic("upgrade", "head")
    assert "identity_adoption_requests" in tables()
    alembic("downgrade", "0021_integration_event_scope")
    assert "identity_adoption_requests" not in tables() and "integration_events" in tables()
    alembic("upgrade", "head")
    assert "identity_adoption_requests" in tables()
