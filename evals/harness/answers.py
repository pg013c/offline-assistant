"""The answer suite (F-06): what /api/chat streamed for each case, and its metrics."""

import json
import re
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from harness.metrics import latency


@dataclass(frozen=True)
class AnswerCase:
    id: str
    language: str
    behaviour: str
    expected_chunk_ids: frozenset[str]
    # Tools any of which should be called, and strings the answer must not hold (F-07).
    tools: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChatResult:
    answer: str
    cited: tuple[str, ...]
    error: str | None
    usage: Mapping[str, Any] | None
    found: bool
    complete: bool
    # Names of the tools the agent called, in order (F-07).
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnswerMetrics:
    # Shares from 0 to 1, gated like the retrieval metrics.
    values: dict[str, float | None]
    cases: dict[str, int]
    # Reported, not gated: they depend on the machine.
    performance: dict[str, float | None]
    missed: dict[str, str] = field(default_factory=dict)
    # Per case: whether it cites an expected chunk, its language, attempts, speed, error.
    per_case: dict[str, dict[str, Any]] = field(default_factory=dict)


def parse_chat_stream(text: str) -> ChatResult:
    """The final attempt's answer, citations, error and usage from a raw /api/chat stream."""
    answer: list[str] = []
    cited: list[str] = []
    error = None
    usage = None
    found = False
    complete = False
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        event = json.loads(line.removeprefix("data:").strip())
        match event.get("type"):
            case "text":
                answer.append(event["text"])
            case "discard":
                answer.clear()
                cited.clear()
            case "citation":
                cited.append(event["chunk_id"])
            case "error":
                error = event["code"]
            case "end":
                usage = event.get("usage")
                found = bool(event.get("found"))
                complete = True
    return ChatResult("".join(answer), tuple(cited), error, usage, found, complete)


# Frequent words of each language (F-06 decision 4); words both write the same way, such as
# "to" and "do", are left out of both.
def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_STOP_WORDS = {
    "pl": _words(
        "i w z na nie się że jest są o od przez dla oraz lub co jak ten ta te który która "
        "które przy po być może musi ich jego jej tym tych także albo jeżeli gdy"
    ),
    "en": _words(
        "the and of in is are for that with as by be on or an this which at from it must "
        "may not their its has have shall when within"
    ),
}
_WORD = re.compile(r"\w+", re.UNICODE)


_POLISH_LETTERS = frozenset("ąćęłńóśźż")


def language_of(text: str) -> str | None:
    """`pl` or `en` by which language's common words the text uses more.

    With no common word of either, Polish letters say Polish and plain letters English;
    an empty text has no language.
    """
    words = [word.lower() for word in _WORD.findall(text)]
    counts = {
        language: sum(word in stop for word in words) for language, stop in _STOP_WORDS.items()
    }
    if counts["pl"] != counts["en"]:
        return max(counts, key=lambda language: counts[language])
    if _POLISH_LETTERS & set(text.lower()):
        return "pl"
    return "en" if words else None


def score_answers(
    cases: Sequence[AnswerCase],
    results: Mapping[str, ChatResult],
    stored: frozenset[str] | None = None,
) -> AnswerMetrics:
    """Citation, language, validity and refusal shares, and the model's speed."""
    answering = [case for case in cases if case.behaviour == "answer"]
    refusing = [case for case in cases if case.behaviour == "refuse"]
    missed: dict[str, str] = {}
    cites = matches = first_try = failed = 0
    attempts: list[float] = []
    first_tokens: list[float] = []
    speeds: list[float] = []
    for case in answering:
        result = results[case.id]
        if result.error or not result.complete:
            failed += 1
            missed[case.id] = f"failed: {result.error or 'the stream ended early'}"
            continue
        usage = result.usage or {}
        attempts.append(float(usage.get("attempts", 1)))
        first_try += usage.get("attempts", 1) == 1
        cites += bool(case.expected_chunk_ids & set(result.cited))
        language = language_of(result.answer)
        matches += language == case.language
        if not case.expected_chunk_ids & set(result.cited):
            missed[case.id] = "cites no expected passage"
        elif language != case.language:
            missed[case.id] = (
                f"answered in {language or 'an unknown language'}, asked in {case.language}"
            )
        if usage.get("first_token_ms") is not None:
            first_tokens.append(float(usage["first_token_ms"]))
            generating = (float(usage["total_ms"]) - float(usage["first_token_ms"])) / 1000
            if generating > 0:
                speeds.append(float(usage["completion_tokens"]) / generating)
    refused = 0
    for case in refusing:
        result = results[case.id]
        if not result.found and result.usage is None:
            refused += 1
        else:
            missed[case.id] = "answered an out-of-scope question"
    first_token = latency(first_tokens)
    per_case = {case.id: _case_result(case, results[case.id]) for case in answering}
    return AnswerMetrics(
        values={
            "cites_expected": _share(cites, len(answering)),
            "language_match": _share(matches, len(answering)),
            "valid_first_try": _share(first_try, len(answering)),
            "answer_failed": _share(failed, len(answering)),
            "out_of_scope_refused": _share(refused, len(refusing)),
        },
        cases={
            "cites_expected": len(answering),
            "language_match": len(answering),
            "valid_first_try": len(answering),
            "answer_failed": len(answering),
            "out_of_scope_refused": len(refusing),
        },
        performance={
            "mean_attempts": statistics.fmean(attempts) if attempts else None,
            "first_token_ms_median": first_token.median_ms,
            "first_token_ms_p95": first_token.p95_ms,
            "tokens_per_second_median": statistics.median(speeds) if speeds else None,
        },
        missed=missed,
        per_case=per_case,
    )


def _case_result(case: AnswerCase, result: ChatResult) -> dict[str, Any]:
    usage = result.usage or {}
    first = usage.get("first_token_ms")
    speed = None
    if first is not None:
        generating = (float(usage["total_ms"]) - float(first)) / 1000
        speed = float(usage["completion_tokens"]) / generating if generating > 0 else None
    return {
        "cites_expected": bool(case.expected_chunk_ids & set(result.cited)),
        "language": language_of(result.answer),
        "attempts": usage.get("attempts"),
        "first_token_ms": first,
        "tokens_per_second": speed,
        "error": result.error,
    }


def answers_markdown(metrics: AnswerMetrics, metadata: Mapping[str, Any]) -> str:
    """The metrics, the model's speed, the missed cases and the run metadata."""
    lines = ["| Metric | Value | Cases |", "|---|---|---|"]
    for name, value in metrics.values.items():
        shown = "n/a" if value is None else f"{value * 100:.1f} %"
        lines.append(f"| {name} | {shown} | {metrics.cases[name]} |")
    lines += ["", "| Performance | Value |", "|---|---|"]
    for name, value in metrics.performance.items():
        shown = (
            "n/a"
            if value is None
            else f"{value:.0f}"
            if name.endswith("_ms_median") or name.endswith("_ms_p95")
            else f"{value:.1f}"
        )
        lines.append(f"| {name} | {shown} |")
    lines += [
        "",
        "| Case | Cites expected | Language | Attempts | First token (ms) | Tokens/s |",
        "|---|---|---|---|---|---|",
    ]
    for case_id, row in metrics.per_case.items():
        cells = [
            "yes" if row["cites_expected"] else "no",
            row["language"] or "?",
            "n/a" if row["attempts"] is None else str(row["attempts"]),
            "n/a" if row["first_token_ms"] is None else f"{row['first_token_ms']:.0f}",
            "n/a" if row["tokens_per_second"] is None else f"{row['tokens_per_second']:.1f}",
        ]
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
    lines += ["", "Missed cases:", ""]
    lines += [f"- {case}: {reason}" for case, reason in metrics.missed.items()] or ["- none"]
    lines += ["", "Run:", ""]
    lines += [f"- {name}: {value}" for name, value in metadata.items()]
    return "\n".join(lines) + "\n"


def _share(count: int, total: int) -> float | None:
    return count / total if total else None
