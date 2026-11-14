"""Runs the deployment smoke script and a short load run against a really spawned local API process."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import load_test  # noqa: E402
import smoke_test  # noqa: E402


@pytest.fixture(scope="module")
def spawned(tmp_path_factory):
    process, base, token, _ = load_test.spawn_api(None, 1, tmp_path_factory.mktemp("api"))
    yield base, token
    process.terminate()
    process.wait(timeout=10)


def test_smoke_script_passes_against_a_running_api(spawned, tmp_path, capsys):
    base, token = spawned
    token_file = tmp_path / "t.txt"
    token_file.write_text(token)
    assert smoke_test.main(["--base-url", base, "--token-file", str(token_file)]) == 0
    assert "checks passed" in capsys.readouterr().out


def test_smoke_script_fails_when_target_is_unreachable(capsys):
    assert smoke_test.main(["--base-url", "http://127.0.0.1:9"]) == 1


def test_short_load_run_reports_percentiles_with_zero_errors(spawned):
    import asyncio
    base, token = spawned
    result = asyncio.run(load_test.run_load(base, token, concurrency=5, duration=3, warmup=1))
    assert result["requests"] > 20 and result["error_rate"] == 0
    overall = result["overall"]
    assert 0 < overall["p50_ms"] <= overall["p95_ms"] <= overall["p99_ms"] <= overall["max_ms"]


def test_percentile_helper():
    assert load_test.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) in (5, 6)
    assert load_test.percentile([7], 99) == 7


def test_budget_gate_accepts_a_good_run_and_flags_each_kind_of_violation():
    result = {"error_rate": 0.0, "throughput_rps": 60.0, "overall": {"p95_ms": 900.0, "p99_ms": 1700.0},
              "by_operation": {"list_suppliers": {"p95_ms": 800.0}, "create_supplier": {"p95_ms": 1200.0}, "ready": {"p95_ms": 300.0}}}
    budget = json.loads((ROOT.parents[1] / "monitoring" / "performance-budget.json").read_text())
    assert load_test.evaluate_budget(result, budget) == []
    slow = {**result, "overall": {"p95_ms": 4500.0, "p99_ms": 7000.0}, "error_rate": 0.05, "throughput_rps": 5.0,
            "by_operation": {"list_suppliers": {"p95_ms": 9000.0}, "create_supplier": {"p95_ms": 1.0}}}
    problems = " | ".join(load_test.evaluate_budget(slow, budget))
    for expected in ("overall p95", "overall p99", "error rate", "throughput", "list_suppliers p95", "operation ready was not exercised"):
        assert expected in problems


def test_load_script_exits_nonzero_when_budget_is_violated(spawned, tmp_path):
    base, token = spawned
    tight = tmp_path / "tight.json"
    tight.write_text('{"overall_p95_ms": 0.001}')
    token_file = tmp_path / "t.txt"
    token_file.write_text(token)
    code = load_test.main(["--base-url", base, "--token-file", str(token_file), "--concurrency", "2", "--duration", "2", "--budget-file", str(tight)])
    assert code == 1
