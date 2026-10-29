import re
from pathlib import Path

import pytest

from harness import run as harness_run
from harness.run import Outcome, RunConfig


def fake_run(tmp_path: Path, failures: list[str]) -> object:
    report = tmp_path / "report.md"
    report.write_text("| Metric | Value | Cases |\n", encoding="utf-8")

    def run(config: RunConfig) -> Outcome:
        return Outcome(tmp_path / "report.json", report, failures)

    return run


def test_make_eval_exits_with_an_error_naming_each_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(harness_run, "run", fake_run(tmp_path, ["mrr dropped from 42.0 to 30.0"]))

    with pytest.raises(SystemExit, match=re.escape("mrr dropped from 42.0 to 30.0")):
        harness_run.main()


def test_without_a_baseline_the_run_says_it_can_become_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(harness_run, "run", fake_run(tmp_path, []))
    monkeypatch.setattr(harness_run, "BASELINE", tmp_path / "missing.json")

    harness_run.main()

    assert "this run can become it" in capsys.readouterr().out
