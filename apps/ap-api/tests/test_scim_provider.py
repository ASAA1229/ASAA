"""SCIM 2.0 adapter against a local fake SCIM server (ASAA-003)."""
from datetime import datetime, timedelta, timezone

import pytest

from asaa_identity import service
from asaa_identity.provider import PermanentProviderError, TransientProviderError, UserAttributes
from asaa_identity.scim import ScimClient, ScimIdentityProvider
from fake_scim import FakeScim
from test_identity_sync import employee, grant, link  # reuse API helpers
from asaa_ap.database import get_db
from asaa_ap.main import app


@pytest.fixture
def fake():
    server = FakeScim().start()
    yield server
    server.stop()


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def provider(fake, sleeps):
    client = ScimClient(fake.url, "test-token", max_retries=3, backoff_base=1.0, sleep=sleeps.append)
    return ScimIdentityProvider(client)


ATTRS = UserAttributes(display_name="Asha Rao", email="asha@example.invalid", employee_reference="E-1")


def test_create_then_update_uses_etag_if_match(provider, fake):
    provider.upsert_user("sub-1", ATTRS, True)
    assert len(fake.users) == 1 and next(iter(fake.users.values()))["userName"] == "sub-1"
    provider.upsert_user("sub-1", UserAttributes(display_name="Asha R."), True)
    assert len(fake.users) == 1
    patch = [r for r in fake.requests if r[0] == "PATCH"]
    assert patch and any(op["path"] == "displayName" and op["value"] == "Asha R." for op in patch[-1][2]["Operations"])
    assert provider.get_user("sub-1").active is True


def test_if_match_header_is_sent_and_stale_etag_is_retried_after_412(provider, fake):
    provider.upsert_user("sub-412", ATTRS, True)
    stale = provider._find_user("sub-412")
    fake.users[stale["id"]]["_v"] += 5  # someone else changed it: our ETag is now stale
    before = len([r for r in fake.requests if r[0] == "PATCH"])
    provider._patch("Users", stale, [{"op": "replace", "path": "active", "value": False}], lambda: provider._find_user("sub-412"))
    assert len([r for r in fake.requests if r[0] == "PATCH"]) - before == 2  # 412 then success with a fresh ETag
    assert provider.get_user("sub-412").active is False


def test_paging_lists_every_user(provider, fake):
    for i in range(5):
        provider.upsert_user(f"sub-{i}", UserAttributes(), True)
    listed = provider.list_users()
    assert sorted(u.subject for u in listed) == [f"sub-{i}" for i in range(5)]
    assert len([r for r in fake.requests if r[0] == "GET" and r[1].endswith("/Users")]) >= 3  # page cap of 2 forced multiple pages


def test_entitlements_map_to_prefixed_groups_and_unmanaged_groups_are_untouched(provider, fake):
    provider.upsert_user("sub-g", ATTRS, True)
    fake.groups["other"] = {"id": "other", "displayName": "payroll-team", "members": [], "_v": 1}
    uid = provider._find_user("sub-g")["id"]
    fake.groups["other"]["members"].append({"value": uid})
    provider.set_entitlements("sub-g", frozenset({"invoice:read", "invoice:approve"}))
    assert provider.get_user("sub-g").entitlements == {"invoice:read", "invoice:approve"}
    provider.set_entitlements("sub-g", frozenset({"invoice:read"}))
    assert provider.get_user("sub-g").entitlements == {"invoice:read"}
    assert any(m["value"] == uid for m in fake.groups["other"]["members"])  # unmanaged membership preserved
    provider.set_entitlements("sub-g", frozenset())
    assert provider.get_user("sub-g").entitlements == frozenset()
    with pytest.raises(PermanentProviderError):
        provider.set_entitlements("missing", frozenset({"x:y"}))


def test_disable_is_idempotent_and_missing_user_is_a_noop(provider, fake):
    provider.upsert_user("sub-d", ATTRS, True)
    provider.disable_user("sub-d")
    patches = len([r for r in fake.requests if r[0] == "PATCH"])
    provider.disable_user("sub-d")
    assert len([r for r in fake.requests if r[0] == "PATCH"]) == patches  # already inactive: no second write
    assert provider.get_user("sub-d").active is False
    provider.disable_user("nobody")
    provider.revoke_sessions("nobody")  # no hook configured: logs, does not raise


def test_session_revoker_hook_is_called(fake):
    seen = []
    p = ScimIdentityProvider(ScimClient(fake.url, "test-token"), session_revoker=seen.append)
    p.revoke_sessions("sub-x")
    assert seen == ["sub-x"]


def test_429_honours_retry_after_and_5xx_backs_off_exponentially(provider, fake, sleeps):
    fake.faults = [(429, {"Retry-After": "7"}), (503, {}), (502, {})]
    provider.upsert_user("sub-r", ATTRS, True)
    assert 7 <= sleeps[0] < 7.8  # Retry-After wins (plus <=10% jitter)
    assert 2.0 <= sleeps[1] < 2.3 and 4.0 <= sleeps[2] < 4.5  # base*2^attempt (+ jitter)
    assert provider.get_user("sub-r") is not None


def test_retries_are_bounded_then_transient_error_for_the_outbox(provider, fake, sleeps):
    fake.faults = [(503, {})] * 10
    with pytest.raises(TransientProviderError):
        provider.get_user("sub-z")
    assert provider.client.attempts == 4 and len(sleeps) == 3  # max_retries=3 -> 4 attempts


def test_auth_and_client_errors_are_permanent_not_retried(fake, sleeps):
    bad = ScimIdentityProvider(ScimClient(fake.url, "wrong-token", sleep=sleeps.append))
    with pytest.raises(PermanentProviderError):
        bad.get_user("x")
    assert bad.client.attempts == 1 and sleeps == []


def test_unreachable_server_is_transient(sleeps):
    p = ScimIdentityProvider(ScimClient("http://127.0.0.1:9/scim/v2", "t", max_retries=1, sleep=sleeps.append, timeout=1))
    with pytest.raises(TransientProviderError):
        p.get_user("x")


def test_https_is_required_for_remote_servers():
    with pytest.raises(ValueError, match="HTTPS"):
        ScimClient("http://idp.example.com/scim/v2", "t")
    ScimClient("https://idp.example.com/scim/v2", "t")
    ScimClient("http://localhost:1/scim/v2", "t")


def test_filter_values_are_escaped(provider, fake):
    nasty = 'a"b\\c'
    provider.upsert_user(nasty, UserAttributes(), True)
    assert provider.get_user(nasty).subject == nasty


def test_outbox_and_reconciliation_work_end_to_end_through_the_scim_adapter(client, fake, provider):
    from test_identity_sync import as_p
    as_p(client)
    session = next(app.dependency_overrides[get_db]())
    emp = employee(client)
    link(client, emp, "sub-scim")
    grant(client, "sub-scim", ("invoice:read", "invoice:approve"))
    now = datetime.now(timezone.utc) + timedelta(seconds=1)
    assert service.process_due(session, provider, "org-a", now=now)["succeeded"] >= 1
    user = provider.get_user("sub-scim")
    assert user.active and user.entitlements == {"invoice:read", "invoice:approve"}
    assert service.reconcile(session, provider, "org-a")["in_sync"]
    # drift behind ASAA's back: extra membership + deactivation of an unlinked-managed state
    provider.set_entitlements("sub-scim", frozenset({"invoice:read", "invoice:approve", "admin:all"}))
    report = service.reconcile(session, provider, "org-a")
    assert report["drift_by_kind"] == {"entitlement_extra": 1}
    service.reconcile(session, provider, "org-a", repair=True)
    service.process_due(session, provider, "org-a", now=datetime.now(timezone.utc) + timedelta(seconds=5))
    assert service.reconcile(session, provider, "org-a")["in_sync"]
    # leaver: provider outage is retried, then access is removed
    from asaa_people.models import Employee
    session.get(Employee, emp["id"]).status = "Inactive"
    service.enqueue_for_employee(session, "org-a", emp["id"], "leaver", "test", "admin")
    session.commit()
    fake.faults = [(503, {})] * 20
    t0 = datetime.now(timezone.utc) + timedelta(minutes=1)
    first = service.process_due(session, provider, "org-a", now=t0)
    assert first["retry_scheduled"] == 1 and provider.client.attempts > 0
    fake.faults = []
    done = service.process_due(session, provider, "org-a", now=t0 + timedelta(hours=1))
    assert done["succeeded"] == 1
    user = provider.get_user("sub-scim")
    assert user.active is False and user.entitlements == frozenset()
    session.close()


def test_scim_provider_is_selected_by_configuration_only(fake):
    from types import SimpleNamespace
    from asaa_identity.bootstrap import register_configured_providers
    from asaa_identity.provider import resolve_provider
    missing = SimpleNamespace(identity_provider="scim", environment="test", scim_base_url=None, scim_bearer_token=None, scim_group_prefix="asaa:")
    with pytest.raises(ValueError, match="required"):
        register_configured_providers(missing)
    cfg = SimpleNamespace(identity_provider="scim", environment="test", scim_base_url=fake.url, scim_bearer_token="test-token", scim_group_prefix="g:")
    register_configured_providers(cfg)
    adapter = resolve_provider("scim")
    adapter.upsert_user("cfg-user", UserAttributes(), True)
    assert adapter.get_user("cfg-user").active and adapter.prefix == "g:"
