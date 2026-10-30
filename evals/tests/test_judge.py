import json
from typing import Any

import httpx
import pytest

from harness.judge import (
    JUDGE_PROMPT,
    JudgeClient,
    JudgedSentence,
    JudgeInput,
    JudgeUnavailable,
    Verdict,
)

INPUT = JudgeInput(
    question="Within how many hours must a breach be notified?",
    key_points=("Within 72 hours where feasible.", "A later notification gives reasons."),
    answer="Within 72 hours [1]. Late notices give reasons [1].",
    sentences=(
        JudgedSentence(index=1, text="Within 72 hours [1].", cites=(1,)),
        JudgedSentence(index=2, text="Late notices give reasons [1].", cites=(1,)),
    ),
    passages={1: "1. ... not later than 72 hours after having become aware of it ..."},
)
VALID = {
    "key_points": [{"index": 1, "made": True}, {"index": 2, "made": True}],
    "reason": "Both key points are made.",
    "sentences": [{"index": 1, "supported": True}, {"index": 2, "supported": True}],
}


class StubJudge:
    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        content = self._replies.pop(0)
        return httpx.Response(
            200,
            json={"choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]},
        )


def client(stub: StubJudge) -> JudgeClient:
    return JudgeClient(
        "http://127.0.0.1:8081", http=httpx.Client(transport=httpx.MockTransport(stub))
    )


def test_the_request_holds_the_prompt_the_schema_and_everything_the_judge_reads() -> None:
    stub = StubJudge(json.dumps(VALID))

    client(stub).judge(INPUT)

    request = stub.requests[0]
    assert request["temperature"] == 0
    assert request["response_format"]["type"] == "json_schema"
    schema = request["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == {"key_points", "reason", "sentences"}
    system, user = request["messages"]
    assert system == {"role": "system", "content": JUDGE_PROMPT}
    for text in (
        INPUT.question,
        "1. Within 72 hours where feasible.",
        "2. Late notices give reasons [1].",
        "[1] 1. ... not later than 72 hours",
    ):
        assert text in user["content"]


def test_a_valid_reply_is_a_verdict() -> None:
    verdict = client(StubJudge(json.dumps(VALID))).judge(INPUT)

    assert verdict == Verdict(
        correctness="correct",
        reason="Both key points are made.",
        supported={1: True, 2: True},
        made={1: True, 2: True},
    )


@pytest.mark.parametrize(
    "invalid",
    [
        "not json",
        json.dumps({**VALID, "key_points": [{"index": 1, "made": True}]}),
        json.dumps({**VALID, "sentences": [{"index": 1, "supported": True}]}),
    ],
)
def test_an_invalid_reply_is_retried(invalid: str) -> None:
    stub = StubJudge(invalid, json.dumps(VALID))

    verdict = client(stub).judge(INPUT)

    assert verdict is not None
    assert len(stub.requests) == 2


def test_after_the_last_retry_the_answer_is_not_judged() -> None:
    stub = StubJudge("no", "still no", "never")

    assert client(stub).judge(INPUT) is None
    assert len(stub.requests) == 3


def test_a_judge_that_does_not_answer_is_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    judge = JudgeClient(
        "http://127.0.0.1:8081", http=httpx.Client(transport=httpx.MockTransport(refuse))
    )

    with pytest.raises(JudgeUnavailable, match="make judge"):
        judge.judge(INPUT)


def test_the_prompt_comes_from_its_file() -> None:
    assert "key points" in JUDGE_PROMPT.lower()
    assert "supported" in JUDGE_PROMPT.lower()


@pytest.mark.parametrize(
    ("made", "correctness"),
    [((True, True), "correct"), ((True, False), "partial"), ((False, False), "wrong")],
)
def test_correctness_follows_from_the_key_points_made(
    made: tuple[bool, bool], correctness: str
) -> None:
    reply = {
        **VALID,
        "key_points": [{"index": index, "made": value} for index, value in enumerate(made, 1)],
    }

    verdict = client(StubJudge(json.dumps(reply))).judge(INPUT)

    assert verdict is not None
    assert verdict.correctness == correctness
