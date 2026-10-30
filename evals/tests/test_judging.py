"""How a run uses the judge (ADR 0022): the health check, the verdicts and a judge that stops."""

import httpx
import pytest

from harness import run
from harness.answers import AnswerCase, ChatResult
from harness.judge import JudgeInput, JudgeUnavailable, Verdict

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

    verdicts, note = run.judge_answers(CASES, QUESTIONS, RESULTS, {}, "http://judge")

    assert verdicts is None
    assert "make judge" in note
