"""Payload screening: credential-looking keys (after Unicode normalisation) and values, depth and numbers."""
import uuid

import pytest

from asaa_integration import screening


def nested(depth):
    value = {"leaf": 1}
    for _ in range(depth):
        value = {"n": value}
    return value


@pytest.mark.parametrize("key", [
    "password", "Password", "PASSWORD", "pass​word", "p‍assword", "ｐａｓｓｗｏｒｄ", "pass_word",
    "passphrase", "pass-phrase", "accessToken", "access_token", "ACCESS-TOKEN", "access_key", "accessKey", "AccessKeyId", "secret_access_key",
    "api key", "api.key", "apiKey", "x-api-key", "session_id", "sessionId", "jwt", "id_jwt", "auth", "x-auth", "ssn", "otp", "totp_seed",
    "client_secret", "private-key", "bearer", "Cookie", "set-cookie", "credentials", "authorization", "pwd", "db_passwd", "refreshToken",
])
def test_secret_looking_keys_are_detected_after_normalisation(key):
    assert screening.key_is_secret_like(key), key
    assert screening.screen({key: "v"}) == [f"data.{key}: key".replace("​", "?").replace("‍", "?")] or screening.screen({key: "v"})


@pytest.mark.parametrize("key", ["author", "authority", "pinned", "files", "durationMs", "brokenAt", "prompt_tokens", "completion_tokens",
                                 "total_tokens", "tokens_used", "title", "commitSha", "branch", "status", "keywords", "monkey"])
def test_ordinary_keys_are_not_flagged(key):
    assert not screening.key_is_secret_like(key), key


@pytest.mark.parametrize("value,kind", [
    ("eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl", "jwt"), ("Authorization: Bearer abcdefghijklmnop", "bearer"),
    ("bearer ABCDEFGH12345678", "bearer"), ("sk-abcdefghijklmnopqrstuvwx", "sk-key"),
    ("ghp_" + "a" * 36, "github-token"), ("github_pat_" + "a" * 30, "github-token"), ("AKIAABCDEFGHIJKLMNOP", "aws-key"),
    ("https://user:hunter2@example.com/path", "url-userinfo"), ("postgresql://svc:pw@db:5432/x", "url-userinfo"),
    ("-----BEGIN RSA PRIVATE KEY-----", "private-key"), ("xoxb-1234567890-abcdefghij", "slack-token"),
    ("eyJhbGciOiJSUzI1NiJ9​.eyJzdWIiOiJ4In0.c2lnbmF0dXJl", "jwt"),
])
def test_credential_shaped_values_are_detected(value, kind):
    findings = screening.screen({"note": value})
    assert findings and findings[0].endswith(kind) and value not in " ".join(findings)


@pytest.mark.parametrize("value", ["generation completed", "https://example.com/path?x=1", "sha 4419b255057349d371cfbabfe8c606b74d9fdd11",
                                   str(uuid.uuid4()), "Bearer", "sk-short", "mailto:someone@example.invalid"])
def test_ordinary_values_are_not_flagged(value):
    assert screening.screen({"note": value, "list": [value]}) == []


def test_screening_helpers_are_iterative_and_bounded():
    assert screening.depth_of(nested(500)) > 500
    assert screening.depth_of({"a": [1, {"b": []}]}) == 4
    assert screening.has_non_finite({"a": [float("inf")]}) and not screening.has_non_finite({"a": [1.5, "nan"]})
    assert screening.screen(nested(500))  # reports nesting instead of recursing forever
    assert len(screening.screen({f"password{i}": "x" for i in range(100)})) <= 20


