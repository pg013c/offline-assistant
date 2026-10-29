import json
from pathlib import Path

import pytest
import yaml

from harness.answers import (
    AnswerCase,
    ChatResult,
    answers_markdown,
    language_of,
    parse_chat_stream,
    score_answers,
)
from harness.promptfoo import outputs_by_case

USAGE: dict[str, object] = {
    "prompt_tokens": 300,
    "completion_tokens": 40,
    "first_token_ms": 400.0,
    "total_ms": 2400.0,
    "attempts": 1,
}


def sse(*events: dict[str, object]) -> str:
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


def citation(chunk_id: str) -> dict[str, object]:
    return {"type": "citation", "chunk_id": chunk_id, "document_id": "d", "quote": "q"}


def end(usage: dict[str, object] | None = USAGE, found: bool = True) -> dict[str, object]:
    return {
        "type": "end",
        "model_id": "qwen3-8b",
        "found": found,
        "is_test_model": False,
        "usage": usage,
    }


def test_a_stream_gives_the_answer_its_citations_and_usage() -> None:
    result = parse_chat_stream(
        sse(
            {"type": "text", "text": "Six "},
            {"type": "text", "text": "months."},
            citation("d:4"),
            end(),
        )
    )

    assert result == ChatResult(
        answer="Six months.", cited=("d:4",), error=None, usage=USAGE, found=True, complete=True
    )


def test_a_discard_drops_the_text_and_citations_before_it() -> None:
    result = parse_chat_stream(
        sse(
            {"type": "text", "text": "Wrong."},
            citation("d:9"),
            {"type": "discard", "reason": "the answer cites no passage"},
            {"type": "text", "text": "Right."},
            citation("d:4"),
            end(),
        )
    )

    assert (result.answer, result.cited) == ("Right.", ("d:4",))


def test_an_error_event_is_kept_and_a_stream_without_end_is_incomplete() -> None:
    failed = parse_chat_stream(
        sse({"type": "error", "code": "invalid_answer", "message": "gave up"}, end(None))
    )
    cut = parse_chat_stream(sse({"type": "text", "text": "Half"}))

    assert failed.error == "invalid_answer"
    assert failed.usage is None
    assert cut.complete is False


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Dostawcy przechowują rejestry zdarzeń przez co najmniej sześć miesięcy.", "pl"),
        ("Administrator zgłasza naruszenie organowi nadzorczemu w ciągu 72 godzin.", "pl"),
        ("Providers keep the logs for at least six months.", "en"),
        # Words both languages write the same way do not count for either.
        ("To jest obowiązek dostawcy.", "pl"),
        ("Do providers keep logs?", "en"),
        ("The controller shall notify the breach within 72 hours.", "en"),
        ("", None),
    ],
)
def test_the_answer_language_is_told_by_its_common_words(text: str, language: str | None) -> None:
    assert language_of(text) == language


def result(
    answer: str, cited: tuple[str, ...], usage: dict[str, object] | None = USAGE, **kw: object
) -> ChatResult:
    fields: dict[str, object] = {"error": None, "found": True, "complete": True}
    fields.update(kw)
    return ChatResult(answer=answer, cited=cited, usage=usage, **fields)  # type: ignore[arg-type]


CASES = [
    AnswerCase("en-a", "en", "answer", frozenset({"d:1"})),
    AnswerCase("pl-b", "pl", "answer", frozenset({"d:2"})),
    AnswerCase("en-c", "en", "answer", frozenset({"d:3"})),
    AnswerCase("oos", "en", "refuse", frozenset()),
]


def test_the_answer_metrics_count_citations_language_validity_and_refusals() -> None:
    results = {
        "en-a": result("Logs are kept six months.", ("d:7", "d:1")),
        "pl-b": result("Logs are kept six months.", ("d:2",), usage={**USAGE, "attempts": 2}),
        "en-c": result("", (), usage=None, error="model_timeout"),
        "oos": result("No relevant passage was found.", (), usage=None, found=False),
    }

    metrics = score_answers(CASES, results)

    assert metrics.values["cites_expected"] == pytest.approx(2 / 3)
    assert metrics.values["language_match"] == pytest.approx(1 / 3)
    assert metrics.values["valid_first_try"] == pytest.approx(1 / 3)
    assert metrics.values["answer_failed"] == pytest.approx(1 / 3)
    assert metrics.values["out_of_scope_refused"] == 1.0
    assert metrics.performance["mean_attempts"] == pytest.approx(1.5)
    assert metrics.performance["first_token_ms_median"] == 400.0
    assert metrics.performance["tokens_per_second_median"] == pytest.approx(20.0)
    assert metrics.missed == {
        "pl-b": "answered in en, asked in pl",
        "en-c": "failed: model_timeout",
    }


def test_an_out_of_scope_case_answered_by_the_model_is_not_refused() -> None:
    metrics = score_answers(
        [AnswerCase("oos", "en", "refuse", frozenset())],
        {"oos": result("Pasta boils for ten minutes.", (), found=True)},
    )

    assert metrics.values["out_of_scope_refused"] == 0.0
    assert metrics.missed == {"oos": "answered an out-of-scope question"}


def test_the_markdown_lists_metrics_performance_and_missed_cases() -> None:
    metrics = score_answers(CASES[:1], {"en-a": result("Logs are kept.", ("d:1",))})

    text = answers_markdown(metrics, {"chat_model": "qwen3-8b"})

    assert "| cites_expected | 100.0 % | 1 |" in text
    assert "| first_token_ms_median | 400 |" in text
    assert "- chat_model: qwen3-8b" in text


def test_promptfoo_outputs_are_read_per_case() -> None:
    results = {
        "results": {
            "results": [
                {"vars": {"case_id": "en-a"}, "response": {"output": "data: {}\n\n"}},
            ]
        }
    }

    assert outputs_by_case(results) == {"en-a": "data: {}\n\n"}


def test_the_answer_suite_posts_questions_to_the_chat_api_and_keeps_the_raw_stream() -> None:
    suite = yaml.safe_load(
        (Path(__file__).parents[1] / "promptfoo" / "answers.yaml").read_text(encoding="utf-8")
    )

    [provider] = suite["providers"]
    assert provider["config"]["url"] == "{{ env.EVAL_API_URL }}/api/chat"
    assert provider["config"]["body"] == {"question": "{{question}}"}
    assert provider["config"]["transformResponse"] == "text"


def test_each_case_is_reported_with_its_own_result() -> None:
    metrics = score_answers(
        CASES[:2],
        {
            "en-a": result("Logs are kept six months.", ("d:1",)),
            "pl-b": result("Logs are kept six months.", ("d:9",), usage={**USAGE, "attempts": 2}),
        },
    )

    assert metrics.per_case["en-a"] == {
        "cites_expected": True,
        "language": "en",
        "attempts": 1,
        "first_token_ms": 400.0,
        "tokens_per_second": 20.0,
        "error": None,
    }
    assert metrics.per_case["pl-b"]["cites_expected"] is False
    text = answers_markdown(metrics, {})
    assert "| Case | Cites expected | Language | Attempts | First token (ms) | Tokens/s |" in text
    assert "| en-a | yes | en | 1 | 400 | 20.0 |" in text
    assert "| pl-b | no | en | 2 | 400 | 20.0 |" in text
