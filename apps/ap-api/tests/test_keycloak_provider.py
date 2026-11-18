"""Keycloak identity adapter against a MOCK Keycloak (tests/fake_keycloak.py). No real Keycloak is contacted."""
import http.client
import json
import logging
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from asaa_ap.config import Settings
from asaa_ap.models import AuditEvent
from asaa_identity import service
from asaa_identity.bootstrap import register_configured_providers
from asaa_identity.keycloak import (KeycloakClient, KeycloakIdentityProvider, _NoRedirect, default_transport, is_protected_group)
from asaa_identity.models import IdentitySyncJob
from asaa_identity.provider import (AuthenticationProviderError, PermanentProviderError, ProviderUser, ProviderUserNotFound,
                                    TransientProviderError, UserAttributes, resolve_provider)
from tests.fake_keycloak import FakeKeycloak
from tests.test_identity_sync import db, employee, grant, link, as_p  # noqa: F401  (db is a fixture)

SECRET = "test-client-secret"
ATTRS = UserAttributes(display_name="Asha Rao", email="asha@example.invalid", employee_reference="E-001", first_name="Asha", last_name="Rao")
JOINER = UserAttributes(display_name="Asha Rao", email="asha@example.invalid", employee_reference="E-001", first_name="Asha", last_name="Rao",
                        allow_reenable=True)


def build(kc=None, create_groups=True, **client_args):
    kc = kc or FakeKeycloak(secret=SECRET)
    sleeps = []
    client = KeycloakClient("http://127.0.0.1:8280", "asaa", "asaa-identity-sync", SECRET, transport=kc, sleep=sleeps.append, **client_args)
    return KeycloakIdentityProvider(client, create_groups=create_groups), kc, sleeps


def sent(kc, method=None, path_part=None):
    return [r for r in kc.requests if (method is None or r["method"] == method) and (path_part is None or path_part in r["path"])
            and "openid-connect" not in r["path"]]


def group_names(kc, user):
    return sorted(kc.groups[g]["name"] for g in kc.memberships[user["id"]])


def attr(user, name):
    return (user.get("attributes") or {}).get(name, [None])[0]


# ============================================================================= joiner

def test_joiner_creates_an_enabled_user_with_required_actions_in_the_base_group_and_no_credentials():
    provider, kc, _ = build()
    provider_id = provider.upsert_user("Sub-Asha", ATTRS, True)
    user = kc.user_by_name("sub-asha")
    assert provider_id == user["id"]
    assert user["enabled"] is True and user["email"] == "asha@example.invalid"
    assert (user["firstName"], user["lastName"]) == ("Asha", "Rao")
    assert user["requiredActions"] == ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]
    assert user["emailVerified"] is False
    assert user["attributes"] == {"asaa_managed": ["true"], "asaa_subject": ["Sub-Asha"], "asaa_employee_reference": ["E-001"]}
    assert "credentials" not in user and group_names(kc, user) == ["employees"]


def test_a_uuid_subject_is_sent_as_the_keycloak_id_and_a_server_that_honours_it_keeps_token_sub_equal():
    provider, kc, _ = build()
    subject = str(uuid.uuid4())
    provider.upsert_user(subject, ATTRS, True)
    assert kc.user_by_name(subject)["id"] == subject
    assert not [s for s in provider.drain_audit() if s["action"] == "id_differs_from_subject"]


def test_a_keycloak_that_ignores_the_supplied_id_is_detected_audited_and_still_found_later():
    kc = FakeKeycloak(secret=SECRET, honor_client_id=False)
    provider, _, _ = build(kc)
    subject = str(uuid.uuid4())
    provider_id = provider.upsert_user(subject, ATTRS, True)
    assert provider_id != subject
    steps = provider.drain_audit()
    assert {"subject": subject, "provider_id": provider_id, "action": "id_differs_from_subject"} in steps
    # Later calls still resolve the same account (by username / asaa_subject), never a second one.
    provider.upsert_user(subject, ATTRS, True)
    assert len(kc.users) == 1 and provider.get_user(subject).provider_id == provider_id


def test_no_password_or_credential_is_ever_sent_to_keycloak():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.set_entitlements("sub-asha", frozenset({"invoice:read"}))
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.disable_user("sub-asha")
    provider.revoke_sessions("sub-asha")
    for request in sent(kc):
        body = (request["body"] or "").lower()
        assert "password" not in body.replace("update_password", "") and "credential" not in body and "secret" not in body
        assert "reset-password" not in request["path"] and "credentials" not in request["path"]


def test_a_single_word_display_name_still_yields_valid_first_and_last_names():
    provider, kc, _ = build()
    provider.upsert_user("sub-x", UserAttributes(display_name="Madonna", email="m@example.invalid"), True)
    user = kc.user_by_name("sub-x")
    assert user["firstName"] == "Madonna" and user["lastName"] == "-"


def test_upsert_is_idempotent_and_preserves_unrelated_attributes_and_required_actions():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    user = kc.user_by_name("sub-asha")
    user["attributes"]["department"] = ["finance"]
    kc.users[user["id"]]["requiredActions"] = []  # the user already completed onboarding
    posts_before = len(sent(kc, "POST", "/users"))
    provider.upsert_user("sub-asha", UserAttributes(email="asha.rao@example.invalid", employee_reference="E-001", first_name="Asha", last_name="Rao"), True)
    updated = kc.user_by_name("sub-asha")
    assert len(sent(kc, "POST", "/users")) == posts_before and len(kc.users) == 1
    assert updated["email"] == "asha.rao@example.invalid" and updated["attributes"]["department"] == ["finance"]
    assert updated["requiredActions"] == []  # never forced again
    assert group_names(kc, updated) == ["employees"] and len(kc.groups) == 1


def test_409_on_create_falls_back_to_update_when_the_account_is_ours(monkeypatch):
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    real, calls = provider._resolve, []
    monkeypatch.setattr(provider, "_resolve", lambda *a, **k: (None, False) if not calls and not calls.append(1) else real(*a, **k))  # race
    provider.upsert_user("sub-asha", UserAttributes(email="new@example.invalid", first_name="Asha", last_name="Rao"), True)
    assert len(kc.users) == 1 and kc.user_by_name("sub-asha")["email"] == "new@example.invalid"


def test_409_for_an_email_owned_by_another_user_is_permanent_and_creates_nothing():
    provider, kc, _ = build()
    provider.upsert_user("sub-one", UserAttributes(email="same@example.invalid", first_name="A", last_name="B"), True)
    with pytest.raises(PermanentProviderError):
        provider.upsert_user("sub-two", UserAttributes(email="same@example.invalid", first_name="C", last_name="D"), True)
    assert kc.user_by_name("sub-two") is None


# ============================================================================= resolution (item 1)

def test_users_are_resolved_by_id_then_username_then_subject_attribute_then_employee_reference():
    provider, kc, _ = build()
    subject = str(uuid.uuid4())
    provider.upsert_user(subject, ATTRS, True)
    user = kc.user_by_name(subject)
    kc.requests.clear()
    assert provider._resolve(subject)[0]["id"] == user["id"] and sent(kc)[0]["path"].endswith(f"/users/{subject}")  # by id first
    user["username"] = "renamed-in-keycloak"
    assert provider._resolve(subject)[0]["id"] == user["id"]  # id still works after a rename
    provider2, kc2, _ = build()
    provider2.upsert_user("sub-asha", ATTRS, True)
    account = kc2.user_by_name("sub-asha")
    account["username"] = "asha.renamed"
    found, owned = provider2._resolve("sub-asha")
    assert found["id"] == account["id"] and owned  # by the asaa_subject attribute
    account["attributes"].pop("asaa_subject")
    found, owned = provider2._resolve("someone-new", "E-001")
    assert found["id"] == account["id"] and owned  # by the employee reference


def test_an_unknown_subject_resolves_to_nothing():
    provider, kc, _ = build()
    assert provider._resolve("ghost", "E-404") == (None, False) and provider.get_user("ghost") is None


def test_ambiguous_employee_references_are_refused():
    provider, kc, _ = build()
    for index in range(2):  # two ASAA-managed accounts that (through a data error) carry the same employee reference
        kc.users[f"u{index}"] = {"id": f"u{index}", "username": f"other-{index}", "enabled": True,
                                 "attributes": {"asaa_managed": ["true"], "asaa_subject": [f"other-{index}"], "asaa_employee_reference": ["E-DUP"]}}
    with pytest.raises(PermanentProviderError):
        provider._resolve("brand-new", "E-DUP")


def test_a_leaver_whose_account_cannot_be_found_is_not_a_silent_success():
    provider, kc, _ = build()
    with pytest.raises(ProviderUserNotFound):
        provider.disable_user("ghost")
    assert provider.drain_audit() == [{"subject": "ghost", "provider_id": None, "action": "not_found", "reason": "leaver account not found"}]


def test_the_not_found_leaver_gets_its_own_outcome_audit_and_alert_through_the_worker(client, db, caplog):
    provider, kc, _ = build()
    as_p(client)
    emp = employee(client, "Lee", "Gone")
    link(client, emp, "sub-gone")
    from asaa_people.models import Employee
    db.get(Employee, emp["id"]).status = "Inactive"
    db.query(IdentitySyncJob).delete()
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "left", "admin")
    db.commit()
    caplog.set_level(logging.ERROR)
    summary = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=5))
    job = db.scalars(select(IdentitySyncJob)).one()
    assert summary["not_found"] == 1 and summary["succeeded"] == 0 and job.status == "NotFound"
    audits = {a.action: a for a in db.scalars(select(AuditEvent))}
    assert audits["identity_sync.not_found"].outcome == "failure" and "identity_sync.completed" not in audits
    assert audits["identity_sync.provisioning_step"].details["action"] == "not_found"
    assert "identity_sync_leaver_account_not_found" in caplog.text
    status = service.status_summary(db, "org-a")
    assert status["not_found"] == 1 and status["alert"] is True


def test_reconciliation_reports_keycloak_ids_that_differ_from_uuid_subjects(client, db):
    kc = FakeKeycloak(secret=SECRET, honor_client_id=False)
    provider, _, _ = build(kc)
    as_p(client)
    subject = str(uuid.uuid4())
    emp = employee(client, "Uma", "Id", "E-77")
    link(client, emp, subject)
    service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=5))
    report = service.reconcile(db, provider, "org-a")
    assert any(d["kind"] == "provider_id_differs_from_subject" and d["subject"] == subject for d in report["drifts"])
    users = {u.subject: u for u in provider.list_users()}
    assert users[subject].provider_id == kc.user_by_name(subject)["id"]  # keyed by the verbatim ASAA subject, not the username


# ============================================================================= ownership (item 4)

def test_an_existing_account_without_asaa_markers_is_never_adopted_or_modified():
    provider, kc, _ = build()
    kc.users["u1"] = {"id": "u1", "username": "sub-asha", "enabled": True, "email": "manual@example.invalid", "attributes": {}}
    kc.memberships["u1"] = set()
    with pytest.raises(PermanentProviderError) as raised:
        provider.upsert_user("sub-asha", ATTRS, True)
    assert "not managed by ASAA" in str(raised.value)
    assert kc.users["u1"] == {"id": "u1", "username": "sub-asha", "enabled": True, "email": "manual@example.invalid", "attributes": {}}
    assert not sent(kc, "PUT") and not sent(kc, "POST")
    with pytest.raises(PermanentProviderError):
        provider.disable_user("sub-asha")  # a leaver on an account ASAA does not own is escalated, not acted on
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    assert kc.users["u1"]["enabled"] is True


def test_an_account_created_by_asaa_is_adopted_by_matching_reference():
    provider, kc, _ = build()
    provider.upsert_user("sub-original", ATTRS, True)
    assert provider._resolve("sub-original", "E-001")[1] is True
    user = kc.user_by_name("sub-original")
    user["attributes"].pop("asaa_managed")
    assert provider._resolve("sub-original", "E-001")[1] is False  # markers are required, a bare reference is not enough


def test_an_account_disabled_outside_asaa_is_not_re_enabled_by_a_mover_or_reconciliation():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    user = kc.user_by_name("sub-asha")
    user["enabled"] = False  # the security team disabled it in the Keycloak console
    with pytest.raises(PermanentProviderError) as raised:
        provider.upsert_user("sub-asha", ATTRS, True)  # mover / reconcile: allow_reenable is False
    assert "outside ASAA" in str(raised.value) and kc.user_by_name("sub-asha")["enabled"] is False


def test_an_explicit_rehire_may_re_enable_and_clears_the_marker():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    kc.user_by_name("sub-asha")["enabled"] = False
    provider.upsert_user("sub-asha", JOINER, True)
    user = kc.user_by_name("sub-asha")
    assert user["enabled"] is True and "asaa_disabled_by_asaa" not in user["attributes"]
    assert provider.drain_audit()[-1]["action"] == "enabled"


def test_an_account_disabled_by_asaa_can_be_re_enabled_by_a_mover():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.disable_user("sub-asha")
    assert attr(kc.user_by_name("sub-asha"), "asaa_disabled_by_asaa") == "true"
    provider.upsert_user("sub-asha", ATTRS, True)  # e.g. leave ended: ASAA's own disable is reversible by ASAA
    assert kc.user_by_name("sub-asha")["enabled"] is True


def test_subjects_that_collide_after_lowercasing_are_refused():
    provider, kc, _ = build()
    provider.upsert_user("Sub-Asha", ATTRS, True)
    with pytest.raises(PermanentProviderError) as raised:
        provider.upsert_user("sub-asha", UserAttributes(email="other@example.invalid", employee_reference="E-OTHER", first_name="O", last_name="T"), True)
    assert "not managed by ASAA" in str(raised.value) or "collides" in str(raised.value)
    assert len(kc.users) == 1 and attr(kc.user_by_name("sub-asha"), "asaa_subject") == "Sub-Asha"


# ============================================================================= entitlements and groups (item 5)

def test_entitlements_map_to_prefixed_groups_and_only_those_are_managed():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    other = kc.add_group("finance-team")
    user = kc.user_by_name("sub-asha")
    kc.memberships[user["id"]].add(other)
    provider.set_entitlements("sub-asha", frozenset({"invoice:read", "invoice:approve"}))
    assert group_names(kc, user) == ["asaa:invoice:approve", "asaa:invoice:read", "employees", "finance-team"]
    provider.set_entitlements("sub-asha", frozenset({"invoice:read"}))
    assert group_names(kc, user) == ["asaa:invoice:read", "employees", "finance-team"]
    provider.set_entitlements("sub-asha", frozenset())
    assert group_names(kc, user) == ["employees", "finance-team"]
    assert provider.get_user("sub-asha").entitlements == frozenset()


def test_set_entitlements_is_idempotent_and_does_not_recreate_groups():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    groups, writes = dict(kc.groups), len(sent(kc, "PUT", "/groups/")) + len(sent(kc, "POST", "/groups"))
    provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    assert kc.groups == groups and len(sent(kc, "PUT", "/groups/")) + len(sent(kc, "POST", "/groups")) == writes


def test_set_entitlements_for_an_unknown_user_is_permanent():
    provider, _, _ = build()
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("ghost", frozenset({"a:b"}))


def test_custom_group_prefix_is_respected():
    kc = FakeKeycloak(secret=SECRET)
    client = KeycloakClient("http://127.0.0.1:8280", "asaa", "asaa-identity-sync", SECRET, transport=kc, sleep=lambda s: None)
    provider = KeycloakIdentityProvider(client, group_prefix="corp/", base_group="staff", create_groups=True)
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.set_entitlements("sub-asha", frozenset({"x:y"}))
    assert group_names(kc, kc.user_by_name("sub-asha")) == ["corp/x:y", "staff"]


@pytest.mark.parametrize("prefix", ["", "   ", "x" * 40, "bad prefix:", "-lead:", "\n"])
def test_an_empty_or_malformed_prefix_is_refused(prefix):
    provider_args = KeycloakClient("http://127.0.0.1:8280", "asaa", "c", "s")
    with pytest.raises(ValueError):
        KeycloakIdentityProvider(provider_args, group_prefix=prefix)


@pytest.mark.parametrize("name", ["hr", "HR", "payroll", "finance", "managers", "auditors", "asaa-administrators", "realm-management",
                                  "jarvis-admin", "portfolio-editors", "templates-ops", "/hr"])
def test_protected_group_names_cannot_be_the_prefix_base_group_or_an_entitlement(name):
    assert is_protected_group(name)
    client = KeycloakClient("http://127.0.0.1:8280", "asaa", "c", "s")
    with pytest.raises(ValueError):
        KeycloakIdentityProvider(client, base_group=name)
    with pytest.raises(ValueError):
        KeycloakIdentityProvider(client, group_prefix=name.strip("/") + ":")
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset({name.strip("/").lower()}))
    assert group_names(kc, kc.user_by_name("sub-asha")) == ["employees"]


@pytest.mark.parametrize("entitlement", ["", "A", "UPPER:case", "has space", "semi;colon", "../etc", "x" * 200, "1starts-with-digit", "new\nline", "a​b"])
def test_malformed_entitlement_names_are_refused_before_anything_changes(entitlement):
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    puts = len(sent(kc, "PUT"))
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset({"good:one", entitlement}))
    assert len(sent(kc, "PUT")) == puts and group_names(kc, kc.user_by_name("sub-asha")) == ["employees"]


def test_groups_are_not_created_unless_explicitly_enabled():
    provider, kc, _ = build(create_groups=False)
    with pytest.raises(PermanentProviderError):
        provider.upsert_user("sub-asha", ATTRS, True)  # even the base group must pre-exist
    kc.add_group("employees")
    provider.upsert_user("sub-asha", ATTRS, True)
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    assert not sent(kc, "POST", "/groups") and "asaa:a:b" not in {g["name"] for g in kc.groups.values()}
    gid = kc.add_group("asaa:a:b")
    provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    assert gid in kc.memberships[kc.user_by_name("sub-asha")["id"]]


def test_a_group_with_role_mappings_is_never_used_for_entitlements_and_nothing_is_added():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    safe = kc.add_group("asaa:safe:one")
    risky = kc.add_group("asaa:risky:one")
    kc.group_roles[risky] = {"realmMappings": [{"name": "realm-admin"}]}
    with pytest.raises(PermanentProviderError) as raised:
        provider.set_entitlements("sub-asha", frozenset({"safe:one", "risky:one"}))
    assert "role mappings" in str(raised.value)
    assert kc.memberships[kc.user_by_name("sub-asha")["id"]] == {next(g for g, v in kc.groups.items() if v["name"] == "employees")}
    assert safe not in kc.memberships[kc.user_by_name("sub-asha")["id"]]  # validated all groups first: no partial change
    kc.group_roles[risky] = {"clientMappings": {"realm-management": {"mappings": [{"name": "manage-users"}]}}}
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset({"risky:one"}))


def test_the_base_group_may_carry_role_mappings_because_that_is_its_purpose():
    provider, kc, _ = build()
    gid = kc.add_group("employees")
    kc.group_roles[gid] = {"realmMappings": [{"name": "employee"}]}
    provider.upsert_user("sub-asha", ATTRS, True)
    assert gid in kc.memberships[kc.user_by_name("sub-asha")["id"]]


# ============================================================================= leaver

def test_leaver_disables_the_user_with_a_minimal_body_and_logs_out_all_sessions():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    user = kc.user_by_name("sub-asha")
    provider.disable_user("sub-asha")
    provider.revoke_sessions("sub-asha")
    assert kc.user_by_name("sub-asha")["enabled"] is False and kc.sessions == {user["id"]: 1}
    assert kc.user_by_name("sub-asha")["email"] == "asha@example.invalid"  # disabled, never deleted
    put = [r for r in sent(kc, "PUT") if r["path"].endswith(f"/users/{user['id']}")][-1]
    assert set(json.loads(put["body"])) == {"enabled", "attributes"}  # no email, names, username or credentials re-sent
    assert sent(kc, "POST", f"/users/{user['id']}/logout")


def test_disable_is_idempotent_for_disabled_accounts_and_revoke_is_a_noop_for_unknown_ones():
    provider, kc, _ = build()
    provider.revoke_sessions("ghost")
    assert not sent(kc, "PUT") and not sent(kc, "POST")
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.disable_user("sub-asha")
    puts = len(sent(kc, "PUT", "/users/"))
    provider.disable_user("sub-asha")
    assert len(sent(kc, "PUT", "/users/")) == puts


def test_get_and_list_users_report_state_provider_id_and_managed_entitlements():
    provider, kc, _ = build()
    provider.upsert_user("sub-a", ATTRS, True)
    provider.upsert_user("sub-b", UserAttributes(email="b@example.invalid", employee_reference="E-B", first_name="B", last_name="B"), True)
    provider.set_entitlements("sub-a", frozenset({"x:y"}))
    provider.disable_user("sub-b")
    users = {u.subject: u for u in provider.list_users()}
    assert users["sub-a"].active and users["sub-a"].entitlements == {"x:y"} and users["sub-b"].active is False
    assert users["sub-a"].provider_id == kc.user_by_name("sub-a")["id"]
    assert provider.get_user("sub-a") == users["sub-a"] and provider.get_user("ghost") is None


def test_list_users_pages_through_all_users():
    provider, kc, _ = build()
    provider.page_size = 2
    for index in range(5):
        provider.upsert_user(f"sub-{index}", UserAttributes(email=f"{index}@example.invalid", employee_reference=f"E-{index}", first_name="A", last_name="B"), True)
    assert sorted(u.subject for u in provider.list_users()) == [f"sub-{i}" for i in range(5)]


# ============================================================================= provisioning audit (item 6)

def test_every_provisioning_step_is_reported_without_personal_data():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.set_entitlements("sub-asha", frozenset({"a:b", "c:d"}))
    provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.disable_user("sub-asha")
    provider.revoke_sessions("sub-asha")
    provider.revoke_sessions("ghost")
    steps = provider.drain_audit()
    uid = kc.user_by_name("sub-asha")["id"]
    assert [s["action"] for s in steps] == ["created", "groups_changed", "groups_changed", "updated", "disabled", "sessions_revoked", "not_found"]
    assert steps[1]["groups_added"] == ["asaa:a:b", "asaa:c:d"] and steps[2]["groups_removed"] == ["asaa:c:d"]
    assert all(s["subject"] in {"sub-asha", "ghost"} for s in steps) and steps[0]["provider_id"] == uid and steps[-1]["provider_id"] is None
    flat = json.dumps(steps)
    for personal in ("asha@example.invalid", "Asha", "Rao", "E-001"):
        assert personal not in flat
    assert provider.drain_audit() == []  # drained


def test_the_worker_writes_one_audit_row_per_step_without_personal_data(client, db):
    provider, kc, _ = build()
    as_p(client)
    emp = employee(client, "Asha", "Rao", code="E-100")
    link(client, emp, "sub-asha")
    grant(client, "sub-asha", ("invoice:read",))
    service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=5))
    rows = db.scalars(select(AuditEvent).where(AuditEvent.action == "identity_sync.provisioning_step")).all()
    assert [r.details["action"] for r in rows][:2] == ["created", "groups_changed"]
    assert rows[0].details["subject"] == "sub-asha" and rows[0].details["provider_id"] == kc.user_by_name("sub-asha")["id"]
    assert rows[1].details["groups_added"] == ["asaa:invoice:read"]
    flat = json.dumps([r.details for r in rows])
    assert "Asha" not in flat and "example.invalid" not in flat and "E-100" not in flat


# ============================================================================= authentication and reliability

def test_expired_token_is_refreshed_once_and_the_call_succeeds():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    issued = kc.token_issued
    kc.expire_tokens()
    assert provider.get_user("sub-asha").active
    assert kc.token_issued == issued + 1


def test_token_is_cached_between_calls():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.get_user("sub-asha")
    assert kc.token_issued == 1


def test_token_is_renewed_before_it_expires():
    now = [0.0]
    kc = FakeKeycloak(secret=SECRET, token_lifetime=100)
    provider, _, _ = build(kc, clock=lambda: now[0])
    provider.get_user("a")
    now[0] = 80.0
    provider.get_user("a")
    assert kc.token_issued == 2


def test_persistent_401_is_an_authentication_error_after_one_refresh():
    provider, kc, _ = build()
    provider.get_user("a")
    kc.valid_tokens.clear()
    kc.secret = "rotated-elsewhere"
    with pytest.raises(AuthenticationProviderError) as raised:
        provider.get_user("a")
    assert SECRET not in str(raised.value) and isinstance(raised.value, TransientProviderError)


def test_wrong_client_secret_is_a_transient_authentication_error_without_leaking_it():
    kc = FakeKeycloak(secret="something-else")
    provider, _, _ = build(kc)
    with pytest.raises(AuthenticationProviderError) as raised:
        provider.get_user("a")
    assert SECRET not in str(raised.value) and "refused the service-account credentials" in str(raised.value)
    assert len(kc.requests) == 1  # no retry storm against a bad credential


def test_403_from_the_admin_api_is_an_authentication_error():
    provider, kc, _ = build()
    kc.fail("GET", r"/users$", 403)
    with pytest.raises(AuthenticationProviderError):
        provider.get_user("a")


def test_5xx_is_retried_with_backoff_then_succeeds():
    provider, kc, sleeps = build()
    kc.fail("GET", r"/users$", 503, times=2)
    assert provider.get_user("nobody") is None
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]
    assert len([r for r in sent(kc, "GET", "/users") if "username=" in r["query"]]) == 3  # two 503s then the answer


def test_retries_are_exhausted_into_a_transient_error():
    provider, kc, sleeps = build(max_retries=2)
    kc.fail("GET", r"/users$", 500, times=10)
    with pytest.raises(TransientProviderError):
        provider.get_user("a")
    assert len(sleeps) == 2


def test_429_honours_retry_after_but_never_beyond_the_backoff_cap():
    provider, kc, sleeps = build()
    kc.fail("GET", r"/users$", 429, times=1, headers={"Retry-After": "7"})
    provider.get_user("a")
    assert 7 <= sleeps[0] <= 7.8
    provider2, kc2, sleeps2 = build(backoff_cap=5.0)
    kc2.fail("GET", r"/users$", 429, times=1, headers={"Retry-After": "86400"})
    provider2.get_user("a")
    assert sleeps2[0] <= 5.5


def test_a_total_per_request_deadline_stops_retrying():
    now = [0.0]
    provider, kc, sleeps = build(clock=lambda: now[0], max_total_seconds=10.0, max_retries=10)
    provider.get_user("a")  # token fetched while the clock is at 0
    kc.fail("GET", r"/users$", 503, times=50)
    original_sleep = provider.client.sleep
    provider.client.sleep = lambda delay: (original_sleep(delay), now.__setitem__(0, now[0] + delay))
    with pytest.raises(TransientProviderError):
        provider.get_user("a")
    assert sum(sleeps) <= 10.5 and len(sleeps) < 10


def test_network_failures_and_http_protocol_errors_are_transient():
    for error in (ConnectionRefusedError("refused"), http.client.RemoteDisconnected("closed"), http.client.IncompleteRead(b"x", 10),
                  http.client.BadStatusLine("garbage"), TimeoutError("slow")):
        def broken(*args, _error=error, **kwargs):
            raise _error

        provider = KeycloakIdentityProvider(KeycloakClient("http://127.0.0.1:8280", "asaa", "c", SECRET, transport=broken, sleep=lambda s: None, max_retries=1))
        with pytest.raises(TransientProviderError):
            provider.get_user("a")


def test_token_endpoint_5xx_is_transient_and_other_failures_are_authentication_errors():
    kc = FakeKeycloak(secret=SECRET)
    kc.token_fault = 503
    provider, _, _ = build(kc, max_retries=1)
    with pytest.raises(TransientProviderError):
        provider.get_user("a")
    for status in (400, 401, 404):
        kc.token_fault = status
        with pytest.raises(AuthenticationProviderError):
            build(kc)[0].get_user("a")


def test_a_non_json_200_on_a_lookup_is_transient_not_a_missing_user():
    provider, kc, _ = build()
    kc.fail("GET", r"/users$", 200, times=1, body=b"<html>login</html>")
    with pytest.raises(TransientProviderError):
        provider.get_user("a")


def test_oversized_responses_are_refused():
    provider, kc, _ = build()
    kc.fail("GET", r"/users$", 200, times=1, body=b"[" + b"1," * 1_200_000 + b"1]")
    with pytest.raises(PermanentProviderError) as raised:
        provider.get_user("a")
    assert "size limit" in str(raised.value)


# ============================================================================= transport hardening (item 2, 8, 9)

def test_redirects_are_a_permanent_error_and_never_followed():
    for status in (301, 302, 307, 308):
        provider, kc, _ = build()
        kc.fail("GET", r"/users$", status, headers={"Location": "http://evil.example/steal"})
        with pytest.raises(PermanentProviderError) as raised:
            provider.get_user("a")
        assert "redirect" in str(raised.value) and "evil.example" not in str(raised.value)
        assert len(sent(kc, "GET", "/users")) == 1  # not retried, not followed
    kc = FakeKeycloak(secret=SECRET)

    def redirecting_token(method, url, headers, body, timeout):
        return 302, {"Location": "https://evil.example/token"}, b""

    provider = KeycloakIdentityProvider(KeycloakClient("http://127.0.0.1:8280", "asaa", "c", SECRET, transport=redirecting_token, sleep=lambda s: None))
    with pytest.raises(PermanentProviderError):
        provider.get_user("a")


def test_the_default_transport_uses_no_redirect_handler_and_no_proxy(monkeypatch):
    seen = {}

    class FakeOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(request.full_url, 302, "Found", {"Location": "http://evil.example"}, None)

    import urllib.error

    def fake_build_opener(*handlers):
        seen["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    status, headers, body = default_transport("GET", "http://127.0.0.1:8280/x", {}, None, 1.0)
    assert status == 302  # surfaced to the client (which refuses it) instead of being followed
    assert _NoRedirect in seen["handlers"]
    proxies = [h for h in seen["handlers"] if isinstance(h, urllib.request.ProxyHandler)]
    assert proxies and proxies[0].proxies == {}
    assert _NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://evil.example") is None


@pytest.mark.parametrize("url", ["http://user:pw@127.0.0.1:8280", "http://127.0.0.1:8280?x=1", "http://127.0.0.1:8280#frag", "http://127.0.0.1:8280;p=1",
                                 "https://user@sso.example.com"])
def test_base_urls_with_credentials_query_fragment_or_params_are_rejected(url):
    with pytest.raises(ValueError):
        KeycloakClient(url, "asaa", "c", "s")


@pytest.mark.parametrize("realm", ["", "a/b", "../master", "a b", "-lead", "x" * 65, "a?b", "a%2Fb", "a\nb"])
def test_realm_names_are_validated(realm):
    with pytest.raises(ValueError):
        KeycloakClient("http://127.0.0.1:8280", realm, "c", "s")


def test_ids_are_percent_encoded_into_paths():
    provider, kc, _ = build()
    provider._group_write("PUT", "user/../../x", "group?id=1&y#z")
    path = sent(kc)[-1]["path"]
    assert "user%2F..%2F..%2Fx" in path and "group%3Fid%3D1%26y%23z" in path and "/../" not in path


def test_group_membership_and_logout_statuses_are_checked():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    kc.fail("PUT", r"/users/[^/]+/groups/", 400)
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    kc.fail("PUT", r"/users/[^/]+/groups/", 404)
    with pytest.raises(TransientProviderError):
        provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    kc.fail("DELETE", r"/users/[^/]+/groups/", 400)
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("sub-asha", frozenset())
    kc.fail("POST", r"/logout$", 400)
    with pytest.raises(PermanentProviderError):
        provider.revoke_sessions("sub-asha")
    kc.fail("POST", r"/logout$", 403)
    with pytest.raises(AuthenticationProviderError):
        provider.revoke_sessions("sub-asha")
    kc.fail("PUT", r"/users/[^/]+$", 400)
    with pytest.raises(PermanentProviderError):
        provider.disable_user("sub-asha")
    assert kc.user_by_name("sub-asha")["enabled"] is True


# ============================================================================= secrets and configuration

def test_the_client_secret_and_tokens_never_reach_logs_errors_or_reprs(caplog):
    caplog.set_level(logging.DEBUG)
    provider, kc, _ = build(max_retries=1)
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.set_entitlements("sub-asha", frozenset({"a:b"}))
    kc.fail("GET", r"/users$", 500, times=5)
    messages = []
    try:
        provider.get_user("sub-asha")
    except Exception as exc:  # noqa: BLE001
        messages.append(str(exc))
    kc.token_fault = 401
    kc.expire_tokens()
    provider.client._token = None
    try:
        provider.get_user("sub-asha")
    except Exception as exc:  # noqa: BLE001
        messages.append(str(exc))
    everything = "\n".join([caplog.text, repr(provider.client), repr(provider), *messages, json.dumps(provider.drain_audit())])
    assert SECRET not in everything and "tok-1" not in everything


def test_secret_is_hidden_in_settings_repr_and_read_from_the_documented_variables(monkeypatch):
    monkeypatch.setenv("ASAA_AP_IDENTITY_PROVIDER", "keycloak")
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_URL", "http://127.0.0.1:8280")
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_REALM", "asaa")
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_CLIENT_SECRET", SECRET)
    settings = Settings()
    assert settings.keycloak_url == "http://127.0.0.1:8280" and settings.keycloak_realm == "asaa"
    assert settings.keycloak_client_id == "asaa-identity-sync" and settings.keycloak_base_group == "employees"
    assert settings.keycloak_create_groups is False  # groups are never created unless explicitly enabled
    assert settings.keycloak_client_secret.get_secret_value() == SECRET
    assert SECRET not in repr(settings) and SECRET not in str(settings.model_dump())
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_CREATE_GROUPS", "true")
    assert Settings().keycloak_create_groups is True


def test_http_is_only_allowed_for_loopback_and_values_are_required():
    for ok in ("https://sso.example.com", "http://localhost:8280", "http://127.0.0.1:8280", "http://[::1]:8280"):
        KeycloakClient(ok, "asaa", "c", "s")
    for bad in ("http://sso.example.com", "ftp://127.0.0.1", "http://127.0.0.1.evil.example", "not a url"):
        with pytest.raises(ValueError):
            KeycloakClient(bad, "asaa", "c", "s")
    for args in (("asaa", "", "s"), ("asaa", "c", "")):
        with pytest.raises(ValueError):
            KeycloakClient("http://127.0.0.1:8280", *args)


def test_bootstrap_registers_the_keycloak_provider_and_requires_url_and_secret():
    class S:
        identity_provider = "keycloak"
        environment = "development"
        scim_group_prefix = "asaa:"
        keycloak_url = None
        keycloak_realm = "asaa"
        keycloak_client_id = "asaa-identity-sync"
        keycloak_base_group = "employees"
        keycloak_create_groups = False

        class keycloak_client_secret:  # noqa: N801
            @staticmethod
            def get_secret_value():
                return SECRET

    with pytest.raises(ValueError):
        register_configured_providers(S)
    S.keycloak_url = "http://127.0.0.1:8280"
    register_configured_providers(S)
    provider = resolve_provider("keycloak")
    assert isinstance(provider, KeycloakIdentityProvider) and provider.create_groups is False
    S.keycloak_client_secret = None
    with pytest.raises(ValueError):
        register_configured_providers(S)
    S.keycloak_client_secret = type("Secret", (), {"get_secret_value": staticmethod(lambda: SECRET)})
    S.scim_group_prefix = ""
    register_configured_providers(S)
    with pytest.raises(ValueError):
        resolve_provider("keycloak")  # an empty prefix fails closed when the provider is built


# ============================================================================= through the real worker contract

def test_hr_lifecycle_drives_keycloak_end_to_end(client, db):
    provider, kc, _ = build()
    as_p(client)
    emp = employee(client, "Asha", "Rao", code="E-100")
    link(client, emp, "sub-asha")
    grant(client, "sub-asha", ("invoice:read",))
    summary = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert summary["dead_lettered"] == 0 and summary["succeeded"] >= 1
    user = kc.user_by_name("sub-asha")
    assert user["enabled"] and (user["firstName"], user["lastName"]) == ("Asha", "Rao")
    assert group_names(kc, user) == ["asaa:invoice:read", "employees"]
    assert user["attributes"]["asaa_employee_reference"] == ["E-100"]
    from asaa_people.models import Employee
    db.get(Employee, emp["id"]).status = "Inactive"
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "left", "admin")
    db.commit()
    service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=2))
    user = kc.user_by_name("sub-asha")
    assert user["enabled"] is False and kc.sessions.get(user["id"]) == 1 and group_names(kc, user) == ["employees"]


def test_a_mover_does_not_revive_an_account_the_security_team_disabled(client, db):
    provider, kc, _ = build()
    as_p(client)
    emp = employee(client, "Cy", "Sec", code="E-9")
    link(client, emp, "sub-cy")
    service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    kc.user_by_name("sub-cy")["enabled"] = False  # disabled in the Keycloak console
    service.enqueue(db, "org-a", "sub-cy", "mover", "role change", "admin")
    db.commit()
    summary = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=10))
    assert summary["dead_lettered"] == 1 and kc.user_by_name("sub-cy")["enabled"] is False


def test_worker_retries_transient_failures(client, db):
    provider, kc, _ = build(max_retries=0)
    as_p(client)
    emp = employee(client, "Bo", "Lee")
    link(client, emp, "sub-bo")
    kc.fail("GET", r"/users$", 503, times=1)
    first = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert first["retry_scheduled"] >= 1 and first["dead_lettered"] == 0


def test_authentication_failures_alert_and_retry_slowly_and_never_dead_letter_a_leaver(client, db, caplog):
    provider, kc, _ = build(max_retries=0)
    as_p(client)
    emp = employee(client, "Di", "Out")
    link(client, emp, "sub-di")
    service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    from asaa_people.models import Employee
    db.get(Employee, emp["id"]).status = "Inactive"
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "left", "admin")
    db.commit()
    kc.fail("GET", r"/users$", 403, times=100)
    caplog.set_level(logging.ERROR)
    moment = datetime.now(timezone.utc) + timedelta(seconds=10)
    for attempt in range(8):  # well past max_attempts
        result = service.process_due(db, provider, "org-a", now=moment)
        job = db.scalars(select(IdentitySyncJob).where(IdentitySyncJob.operation == "leaver")).one()
        assert job.status == "Pending" and result["dead_lettered"] == 0
        assert job.next_attempt_at.replace(tzinfo=timezone.utc) >= moment + timedelta(seconds=service.AUTH_FAILURE_BACKOFF_SECONDS)
        moment = job.next_attempt_at.replace(tzinfo=timezone.utc) + timedelta(seconds=1)
    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "identity_sync.provider_auth_failed")).all()
    assert "identity_provider_auth_failure" in caplog.text and SECRET not in caplog.text
    kc.faults.clear()  # the credential is fixed: the leaver finally completes
    service.process_due(db, provider, "org-a", now=moment)
    assert kc.user_by_name("sub-di")["enabled"] is False


def test_a_joiner_exhausts_its_budget_on_persistent_auth_failures_but_a_leaver_does_not(client, db):
    provider, kc, _ = build(max_retries=0)
    as_p(client)
    emp = employee(client, "Jo", "In")
    link(client, emp, "sub-jo")
    kc.fail("GET", r"/users$", 401, times=100)
    kc.secret = "rotated"
    moment = datetime.now(timezone.utc) + timedelta(seconds=1)
    for _ in range(6):
        service.process_due(db, provider, "org-a", now=moment)
        moment += timedelta(days=1)
    job = db.scalars(select(IdentitySyncJob).where(IdentitySyncJob.operation == "joiner")).one()
    assert job.status == "DeadLetter"


def test_an_unexpected_exception_in_one_job_cannot_stop_the_others(client, db):
    class Flaky(KeycloakIdentityProvider):
        def upsert_user(self, subject, attributes, active):
            if subject == "sub-boom":
                raise RuntimeError("bug with asha@example.invalid token=abc123")
            return super().upsert_user(subject, attributes, active)

    kc = FakeKeycloak(secret=SECRET)
    provider = Flaky(KeycloakClient("http://127.0.0.1:8280", "asaa", "c", SECRET, transport=kc, sleep=lambda s: None), create_groups=True)
    as_p(client)
    boom = employee(client, "Bo", "Om", "E-1")
    link(client, boom, "sub-boom")
    fine = employee(client, "Fi", "Ne", "E-2")
    link(client, fine, "sub-fine")
    summary = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert summary["processed"] == 2 and summary["succeeded"] == 1 and summary["retry_scheduled"] == 1
    assert kc.user_by_name("sub-fine") is not None and kc.user_by_name("sub-boom") is None
    failed = db.scalars(select(IdentitySyncJob).where(IdentitySyncJob.subject == "sub-boom")).one()
    assert failed.status == "Pending" and failed.last_error == "unexpected: RuntimeError"  # type only, no message or personal data
