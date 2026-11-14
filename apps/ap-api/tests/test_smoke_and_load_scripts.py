"""Runs the deployment smoke script and a short load run against a really spawned local API process."""
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
