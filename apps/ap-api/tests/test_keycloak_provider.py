"""Keycloak identity adapter against a MOCK Keycloak (tests/fake_keycloak.py). No real Keycloak is contacted."""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from asaa_ap.config import Settings
from asaa_identity import service
from asaa_identity.bootstrap import register_configured_providers
from asaa_identity.keycloak import KeycloakClient, KeycloakIdentityProvider
from asaa_identity.provider import PermanentProviderError, TransientProviderError, UserAttributes, resolve_provider
from tests.fake_keycloak import FakeKeycloak
from tests.test_identity_sync import db, employee, grant, link, as_p  # noqa: F401  (db is a fixture)

SECRET = "test-client-secret"
ATTRS = UserAttributes(display_name="Asha Rao", email="asha@example.invalid", employee_reference="E-001", first_name="Asha", last_name="Rao")


def build(kc=None, **client_args):
    kc = kc or FakeKeycloak(secret=SECRET)
    sleeps = []
    client = KeycloakClient("http://127.0.0.1:8280", "asaa", "asaa-identity-sync", SECRET, transport=kc, sleep=sleeps.append, **client_args)
    return KeycloakIdentityProvider(client), kc, sleeps


def sent(kc, method=None, path_part=None):
    return [r for r in kc.requests if (method is None or r["method"] == method) and (path_part is None or path_part in r["path"])
            and "openid-connect" not in r["path"]]


def group_names(kc, user):
    return sorted(kc.groups[g]["name"] for g in kc.memberships[user["id"]])


# ----------------------------------------------------------------------------- joiner

def test_joiner_creates_an_enabled_user_with_required_actions_in_the_base_group_and_no_credentials():
    provider, kc, _ = build()
    provider.upsert_user("Sub-Asha", ATTRS, True)
    user = kc.user_by_name("sub-asha")
    assert user["enabled"] is True and user["email"] == "asha@example.invalid"
    assert (user["firstName"], user["lastName"]) == ("Asha", "Rao")
    assert user["requiredActions"] == ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]
    assert user["emailVerified"] is False and user["attributes"] == {"asaa_employee_reference": ["E-001"]}
    assert "credentials" not in user
    assert group_names(kc, user) == ["employees"]


def test_a_uuid_subject_becomes_the_keycloak_user_id_so_token_sub_matches():
    provider, kc, _ = build()
    subject = str(uuid.uuid4())
    provider.upsert_user(subject, ATTRS, True)
    assert kc.user_by_name(subject)["id"] == subject


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
    provider.upsert_user("sub-asha", UserAttributes(display_name="Asha Rao", email="asha.rao@example.invalid", employee_reference="E-001",
                                                    first_name="Asha", last_name="Rao"), True)
    updated = kc.user_by_name("sub-asha")
    assert len(sent(kc, "POST", "/users")) == posts_before and len(kc.users) == 1
    assert updated["email"] == "asha.rao@example.invalid" and updated["attributes"]["department"] == ["finance"]
    assert updated["requiredActions"] == []  # never forced again
    assert group_names(kc, updated) == ["employees"] and len(kc.groups) == 1


def test_409_on_create_falls_back_to_update_when_the_user_exists(monkeypatch):
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    real, calls = provider._find_user, []
    monkeypatch.setattr(provider, "_find_user", lambda s: None if not calls and not calls.append(1) else real(s))  # race: not visible once
    provider.upsert_user("sub-asha", UserAttributes(email="new@example.invalid", first_name="Asha", last_name="Rao"), True)
    assert len(kc.users) == 1 and kc.user_by_name("sub-asha")["email"] == "new@example.invalid"


def test_409_for_an_email_owned_by_another_user_is_permanent_and_creates_nothing():
    provider, kc, _ = build()
    provider.upsert_user("sub-one", ATTRS, True)
    with pytest.raises(PermanentProviderError):
        provider.upsert_user("sub-two", ATTRS, True)
    assert kc.user_by_name("sub-two") is None


# ----------------------------------------------------------------------------- mover

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
    provider = KeycloakIdentityProvider(client, group_prefix="corp/", base_group="staff")
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.set_entitlements("sub-asha", frozenset({"x"}))
    assert group_names(kc, kc.user_by_name("sub-asha")) == ["corp/x", "staff"]


# ----------------------------------------------------------------------------- leaver

def test_leaver_disables_the_user_and_logs_out_all_sessions():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    user = kc.user_by_name("sub-asha")
    provider.disable_user("sub-asha")
    provider.revoke_sessions("sub-asha")
    assert kc.user_by_name("sub-asha")["enabled"] is False and kc.sessions == {user["id"]: 1}
    assert kc.user_by_name("sub-asha")["email"] == "asha@example.invalid"  # disabled, never deleted
    assert sent(kc, "POST", f"/users/{user['id']}/logout")


def test_disable_and_revoke_are_noops_for_unknown_users_and_idempotent_for_disabled_ones():
    provider, kc, _ = build()
    provider.disable_user("ghost")
    provider.revoke_sessions("ghost")
    assert not sent(kc, "PUT") and not sent(kc, "POST")
    provider.upsert_user("sub-asha", ATTRS, True)
    provider.disable_user("sub-asha")
    puts = len(sent(kc, "PUT", "/users/"))
    provider.disable_user("sub-asha")
    assert len(sent(kc, "PUT", "/users/")) == puts


def test_get_and_list_users_report_state_and_managed_entitlements():
    provider, kc, _ = build()
    provider.upsert_user("sub-a", ATTRS, True)
    provider.upsert_user("sub-b", UserAttributes(email="b@example.invalid", first_name="B", last_name="B"), True)
    provider.set_entitlements("sub-a", frozenset({"x:y"}))
    provider.disable_user("sub-b")
    users = {u.subject: u for u in provider.list_users()}
    assert users["sub-a"].active and users["sub-a"].entitlements == {"x:y"} and users["sub-b"].active is False
    assert provider.get_user("sub-a") == users["sub-a"] and provider.get_user("ghost") is None


def test_list_users_pages_through_all_users():
    provider, kc, _ = build()
    provider.page_size = 2
    for index in range(5):
        provider.upsert_user(f"sub-{index}", UserAttributes(email=f"{index}@example.invalid", first_name="A", last_name="B"), True)
    assert sorted(u.subject for u in provider.list_users()) == [f"sub-{i}" for i in range(5)]


# ----------------------------------------------------------------------------- authentication and reliability

def test_expired_token_is_refreshed_once_and_the_call_succeeds():
    provider, kc, _ = build()
    provider.upsert_user("sub-asha", ATTRS, True)
    issued = kc.token_issued
    kc.expire_tokens()  # Keycloak now rejects the cached token with 401
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
    assert kc.token_issued == 2  # 100 s lifetime minus a 30 s safety margin


def test_persistent_401_is_permanent_after_one_refresh():
    provider, kc, _ = build()
    provider.get_user("a")
    kc.valid_tokens.clear()
    kc.secret = "rotated-elsewhere"  # the configured secret no longer works
    with pytest.raises(PermanentProviderError) as raised:
        provider.get_user("a")
    assert SECRET not in str(raised.value)


def test_wrong_client_secret_is_a_permanent_error_without_leaking_it():
    kc = FakeKeycloak(secret="something-else")
    provider, _, _ = build(kc)
    with pytest.raises(PermanentProviderError) as raised:
        provider.get_user("a")
    assert SECRET not in str(raised.value) and "token request was rejected" in str(raised.value)
    assert len(kc.requests) == 1  # no retry storm against a bad credential


def test_403_from_the_admin_api_is_permanent():
    provider, kc, _ = build()
    kc.fail("GET", r"/users$", 403)
    with pytest.raises(PermanentProviderError):
        provider.get_user("a")


def test_5xx_is_retried_with_backoff_then_succeeds():
    provider, kc, sleeps = build()
    kc.fail("GET", r"/users$", 503, times=2)
    assert provider.get_user("nobody") is None
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]
    assert len(sent(kc, "GET", "/users")) == 3


def test_retries_are_exhausted_into_a_transient_error():
    provider, kc, sleeps = build(max_retries=2)
    kc.fail("GET", r"/users$", 500, times=10)
    with pytest.raises(TransientProviderError):
        provider.get_user("a")
    assert len(sleeps) == 2


def test_429_honours_retry_after():
    provider, kc, sleeps = build()
    kc.fail("GET", r"/users$", 429, times=1, headers={"Retry-After": "7"})
    provider.get_user("a")
    assert 7 <= sleeps[0] <= 7.8


def test_network_failures_are_transient():
    kc = FakeKeycloak(secret=SECRET)

    def broken(*args, **kwargs):
        raise ConnectionRefusedError("refused")

    provider = KeycloakIdentityProvider(KeycloakClient("http://127.0.0.1:8280", "asaa", "c", SECRET, transport=broken, sleep=lambda s: None, max_retries=1))
    with pytest.raises(TransientProviderError):
        provider.get_user("a")


def test_token_endpoint_5xx_is_transient_and_other_failures_permanent():
    kc = FakeKeycloak(secret=SECRET)
    kc.token_fault = 503
    provider, _, _ = build(kc, max_retries=1)
    with pytest.raises(TransientProviderError):
        provider.get_user("a")
    kc.token_fault = 400
    with pytest.raises(PermanentProviderError):
        build(kc)[0].get_user("a")


# ----------------------------------------------------------------------------- secrets and configuration

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
    everything = "\n".join([caplog.text, repr(provider.client), repr(provider), *messages])
    assert SECRET not in everything and "tok-1" not in everything


def test_secret_is_hidden_in_settings_repr_and_read_from_the_documented_variables(monkeypatch):
    monkeypatch.setenv("ASAA_AP_IDENTITY_PROVIDER", "keycloak")
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_URL", "http://127.0.0.1:8280")
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_REALM", "asaa")
    monkeypatch.setenv("ASAA_IDENTITY_KEYCLOAK_CLIENT_SECRET", SECRET)
    settings = Settings()
    assert settings.keycloak_url == "http://127.0.0.1:8280" and settings.keycloak_realm == "asaa"
    assert settings.keycloak_client_id == "asaa-identity-sync" and settings.keycloak_base_group == "employees"
    assert settings.keycloak_client_secret.get_secret_value() == SECRET
    assert SECRET not in repr(settings) and SECRET not in str(settings.model_dump())


def test_http_is_only_allowed_for_loopback_and_values_are_required():
    for ok in ("https://sso.example.com", "http://localhost:8280", "http://127.0.0.1:8280", "http://[::1]:8280"):
        KeycloakClient(ok, "asaa", "c", "s")
    for bad in ("http://sso.example.com", "ftp://127.0.0.1", "http://127.0.0.1.evil.example", "not a url"):
        with pytest.raises(ValueError):
            KeycloakClient(bad, "asaa", "c", "s")
    for args in (("", "c", "s"), ("asaa", "", "s"), ("asaa", "c", "")):
        with pytest.raises(ValueError):
            KeycloakClient("http://127.0.0.1:8280", *args)


def test_bootstrap_registers_the_keycloak_provider_and_requires_url_and_secret(monkeypatch):
    class S:
        identity_provider = "keycloak"
        environment = "development"
        scim_group_prefix = "asaa:"
        keycloak_url = None
        keycloak_realm = "asaa"
        keycloak_client_id = "asaa-identity-sync"
        keycloak_base_group = "employees"

        class keycloak_client_secret:  # noqa: N801
            @staticmethod
            def get_secret_value():
                return SECRET

    with pytest.raises(ValueError):
        register_configured_providers(S)
    S.keycloak_url = "http://127.0.0.1:8280"
    register_configured_providers(S)
    assert isinstance(resolve_provider("keycloak"), KeycloakIdentityProvider)
    S.keycloak_client_secret = None
    with pytest.raises(ValueError):
        register_configured_providers(S)


# ----------------------------------------------------------------------------- through the real worker contract

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
    # leaver
    from asaa_people.models import Employee
    db.get(Employee, emp["id"]).status = "Inactive"
    service.enqueue_for_employee(db, "org-a", emp["id"], "leaver", "left", "admin")
    db.commit()
    service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=2))
    user = kc.user_by_name("sub-asha")
    assert user["enabled"] is False and kc.sessions.get(user["id"]) == 1 and group_names(kc, user) == ["employees"]


def test_worker_retries_transient_failures_and_dead_letters_permanent_ones(client, db):
    provider, kc, _ = build(max_retries=0)
    as_p(client)
    emp = employee(client, "Bo", "Lee")
    link(client, emp, "sub-bo")
    kc.fail("GET", r"/users$", 503, times=1)
    first = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert first["retry_scheduled"] >= 1 and first["dead_lettered"] == 0
    kc.fail("GET", r"/users$", 403, times=5)
    second = service.process_due(db, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(days=1))
    assert second["dead_lettered"] >= 1
