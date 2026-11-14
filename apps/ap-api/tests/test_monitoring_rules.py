"""Static checks for the Prometheus rules/tests and the JSON log schema (ASAA-011).

promtool itself is not run here (it needs the promtool binary/Docker); CI job `alert-rules-promtool` runs
`promtool check rules` and `promtool test rules`. These tests guard what promtool cannot: that rules only reference
metrics the API really emits, that every alert is covered by a unit test and annotated, and that real log lines
satisfy the published schema.
"""
import json
import logging
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient

import asaa_ap.main as main
from asaa_ap.main import app
from asaa_ap.observability import JsonFormatter, metrics
from asaa_ap.security import Principal, get_principal

ROOT = Path(__file__).resolve().parents[3]
RULES = yaml.safe_load((ROOT / "monitoring" / "asaa-alerts.yml").read_text())
RULE_TESTS = yaml.safe_load((ROOT / "monitoring" / "asaa-alerts.test.yml").read_text())
SCHEMA = json.loads((ROOT / "monitoring" / "log-schema.json").read_text())
ALERTS = [rule for group in RULES["groups"] for rule in group["rules"]]


def test_every_alert_has_severity_summary_runbook_and_expression():
    assert len(ALERTS) >= 6
    for rule in ALERTS:
        assert rule["labels"]["severity"] in {"critical", "warning"}, rule["alert"]
        assert rule["annotations"]["summary"] and rule["annotations"]["runbook"].startswith("docs/"), rule["alert"]
        assert rule["expr"].strip()
    assert len({r["alert"] for r in ALERTS}) == len(ALERTS)


def test_runbook_references_point_at_existing_documents():
    for rule in ALERTS:
        document = rule["annotations"]["runbook"].split("#")[0]
        assert (ROOT / document).exists(), rule["alert"]


def test_every_alert_is_exercised_by_a_promtool_unit_test():
    tested = {case["alertname"] for t in RULE_TESTS["tests"] for case in t["alert_rule_test"]}
    assert {r["alert"] for r in ALERTS} <= tested
    firing = {case["alertname"] for t in RULE_TESTS["tests"] for case in t["alert_rule_test"] if case["exp_alerts"]}
    assert {r["alert"] for r in ALERTS} <= firing, "each alert needs at least one test where it fires"


def test_unit_test_annotations_match_the_rules_exactly():
    by_name = {r["alert"]: r for r in ALERTS}
    for t in RULE_TESTS["tests"]:
        for case in t["alert_rule_test"]:
            for expected in case["exp_alerts"]:
                assert expected["exp_annotations"] == by_name[case["alertname"]]["annotations"]
                assert expected["exp_labels"]["severity"] == by_name[case["alertname"]]["labels"]["severity"]


def emitted_metric_names(client):
    metrics.reset()
    client.get("/health")
    body = client.get("/metrics").text
    names = set(re.findall(r"^# TYPE (\w+) ", body, re.M))
    names |= {n + suffix for n in list(names) for suffix in ("_bucket", "_sum", "_count")}
    return names | {"up"}


def test_rules_and_tests_reference_only_metrics_the_api_emits(client, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(environment="development", metrics_token=None))
    known = emitted_metric_names(client)
    promql_words = {"rate", "sum", "by", "histogram_quantile", "resets", "le", "status", "job", "for"}
    for rule in ALERTS:
        for token in re.findall(r"\b([a-z_][a-z0-9_]*)\b(?=\s*[{\[(]|\s*[<>=]|\s*$|\s*/|\s*\))", rule["expr"]):
            if token.startswith("asaa_"):
                assert token in known, f"{rule['alert']} references unknown metric {token}"
    for t in RULE_TESTS["tests"]:
        for series in t["input_series"]:
            name = re.match(r"^([a-z_0-9]+)", series["series"]).group(1)
            assert name in known, f"unit test uses unknown metric {name}"
    # label values used in rules must be ones the middleware can emit
    body = client.get("/metrics").text
    assert 'status="200"' in body and 'le="1.0"' in body


@pytest.fixture
def schema_validator():
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


@pytest.fixture
def captured_lines():
    lines = []

    class Capture(logging.Handler):
        def emit(self, record):
            lines.append(JsonFormatter().format(record))

    handler = Capture()
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield lines
    root.removeHandler(handler)
    root.setLevel(previous)


def test_real_log_lines_conform_to_the_published_schema(client, schema_validator, captured_lines, monkeypatch):
    client.get("/api/v1/ap/suppliers?access_token=secret", headers={"X-Request-ID": "trace-00000001"})  # access log
    app.dependency_overrides[get_principal] = lambda: Principal("nobody", "org-a", frozenset())
    client.get("/api/v1/ap/suppliers")  # 403 path
    from asaa_ap.database import get_db

    def exploding():
        raise RuntimeError("boom token=abc")
        yield  # pragma: no cover
    app.dependency_overrides[get_db] = exploding
    TestClient(app, raise_server_exceptions=False).get("/api/v1/ap/suppliers")  # unhandled exception log

    class Broken:
        def connect(self):
            from sqlalchemy.exc import OperationalError
            raise OperationalError("SELECT 1", {}, Exception("down"))
    monkeypatch.setattr(main, "engine", Broken())
    client.get("/ready")  # readiness failure log
    records = [json.loads(line) for line in captured_lines]
    messages = {r["message"] for r in records}
    assert {"request", "unhandled_exception", "readiness_check_failed"} <= messages
    for record in records:
        errors = sorted(e.message for e in schema_validator.iter_errors(record))
        assert errors == [], (record, errors)
    exc = next(r for r in records if r["message"] == "unhandled_exception")
    assert exc["exception"]["type"] == "RuntimeError" and "abc" not in exc["exception"]["message"]


def test_schema_rejects_malformed_or_leaky_lines(schema_validator):
    good = {"timestamp": "2026-11-14T10:00:00.123Z", "level": "INFO", "logger": "asaa.request", "message": "request",
            "request_id": "abcdefgh12", "method": "GET", "path": "/api/v1/x", "status": 200, "duration_ms": 1.5}
    assert list(schema_validator.iter_errors(good)) == []
    bad_cases = [
        {k: v for k, v in good.items() if k != "request_id"},
        {**good, "timestamp": "yesterday"},
        {**good, "level": "LOUD"},
        {**good, "path": "/x?token=abc"},  # query strings must never be logged
        {**good, "status": "200"},
        {**good, "request_id": "bad id with spaces"},
        {**good, "exception": {"type": "X"}},
    ]
    for case in bad_cases:
        assert list(schema_validator.iter_errors(case)), case
