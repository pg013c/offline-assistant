"""How a run uses the judge (ADR 0022): the health check, the verdicts and a judge that stops."""

import hashlib
from pathlib import Path

import httpx
import pytest

from harness import run
from harness.answers import AnswerCase, ChatResult
from harness.calibration import Agreement
from harness.judge import JUDGE_PROMPT, JudgeInput, JudgeUnavailable, Verdict

CASES = [
    AnswerCase("a", "en", "answer", frozenset({"d:1"}), key_points=("x",)),
    AnswerCase("b", "en", "answer", frozenset({"d:2"}), key_points=("y",)),
    AnswerCase("oos", "en", "refuse", frozenset()),
]
QUESTIONS = {"a": "A?", "b": "B?", "oos": "Weather?"}


def answered(text: str) -> ChatResult:
    return ChatResult(answer=text, cited=("d:1",), usage={}, error=None, found=True, complete=True)


RESULTS = {"a": answered("A [1]."), "b": answered("B [1]."), "oos": answered("")}
VERDICT = Verdict("correct", "All points.", {1: True})


class FakeJudge:
    """Answers `verdicts` calls, then stops answering."""

    def __init__(self, verdicts: int) -> None:
        self.left = verdicts
        self.judged: list[JudgeInput] = []
        self.thought = True

    def __call__(self, url: str) -> "FakeJudge":
        return self

    def judge(self, judged: JudgeInput) -> Verdict | None:
        if self.left == 0:
            raise JudgeUnavailable("No judge answers. Start it with: make judge")
        self.left -= 1
        self.judged.append(judged)
        return VERDICT


@pytest.fixture
def healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda url, **_: httpx.Response(200, request=httpx.Request("GET", url))
    )


@pytest.mark.usefixtures("healthy")
def test_a_judge_that_stops_answering_mid_run_skips_the_judged_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run, "JudgeClient", FakeJudge(verdicts=1))

    verdicts, judge = run.judge_answers(CASES, QUESTIONS, RESULTS, {}, "http://judge")

    assert verdicts is None
    assert "make judge" in judge["skipped"]


def test_without_a_judge_the_note_says_how_to_start_it(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(url: str, **_: object) -> httpx.Response:
        raise httpx.ConnectError("refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", down)

    verdicts, judge = run.judge_answers(CASES, QUESTIONS, RESULTS, {}, "http://judge")

    assert verdicts is None
    assert judge == {"skipped": "no judge answers at http://judge; start it with make judge"}


@pytest.mark.usefixtures("healthy")
def test_the_judge_rules_on_each_completed_answer_only(monkeypatch: pytest.MonkeyPatch) -> None:
    judge = FakeJudge(verdicts=5)
    monkeypatch.setattr(run, "JudgeClient", judge)
    failed = ChatResult(answer="", cited=(), usage=None, error="x", found=False, complete=False)

    verdicts, identity = run.judge_answers(
        CASES, QUESTIONS, {**RESULTS, "b": failed}, {"d:1": "Text."}, "http://judge"
    )

    assert verdicts == {"a": VERDICT}
    assert [judged.question for judged in judge.judged] == ["A?"]
    assert identity == {
        "model": "qwen3-30b-a3b",
        "server": {"url": "http://judge"},
        "prompt_sha256": hashlib.sha256(JUDGE_PROMPT.encode()).hexdigest(),
        "max_tokens": 8192,
        "thinking": True,
    }


def test_without_its_calibration_set_the_judge_is_not_calibrated(tmp_path: Path) -> None:
    assert run.calibrate("http://judge", tmp_path / "missing.yaml") is None


def test_a_judge_that_stops_during_calibration_is_not_calibrated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run, "JudgeClient", FakeJudge(verdicts=3))

    assert run.calibrate("http://judge") is None


BELOW = Agreement(correctness=0.8, support=0.9, items=20)
ABOVE = Agreement(correctness=0.9, support=0.9, items=20)
JUDGED = {"cites_expected": 0.9, "judged_correct": 0.65, "citation_support": 0.95}


def test_judged_metrics_without_calibration_fail_the_run() -> None:
    failures = run.answer_failures(JUDGED, {}, calibration=None, judged=True)

    assert failures == ["the judge was not calibrated: its calibration set did not run (ADR 0022)"]


def test_a_judge_below_the_bar_fails_the_run() -> None:
    failures = run.answer_failures(JUDGED, {}, calibration=BELOW, judged=True)

    assert failures == [
        "the judge agrees with the calibration set on 80.0 % of correctness verdicts, "
        "below 85 % (ADR 0022)"
    ]


def test_an_unjudged_run_needs_no_calibration() -> None:
    unjudged = {**JUDGED, "judged_correct": None, "citation_support": None}

    assert run.answer_failures(unjudged, {}, calibration=None, judged=False) == []


def test_metrics_from_a_judge_below_the_bar_are_set_apart() -> None:
    values, untrusted = run.trusted_judged(JUDGED, BELOW)

    assert values == {"cites_expected": 0.9, "judged_correct": None, "citation_support": None}
    assert untrusted == {"judged_correct": 0.65, "citation_support": 0.95}


def test_metrics_from_a_calibrated_judge_are_kept() -> None:
    assert run.trusted_judged(JUDGED, ABOVE) == (JUDGED, {})
