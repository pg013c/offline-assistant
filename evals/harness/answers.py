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


@dataclass(frozen=True)
class ChatResult:
    answer: str
    cited: tuple[str, ...]
    error: str | None
    usage: Mapping[str, Any] | None
    found: bool
    complete: bool


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


# Frequent words of each language that the other does not use (F-06 decision 4).
def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_STOP_WORDS = {
    "pl": _words(
        "i w z na do nie się że jest są o od przez dla oraz lub co jak ten ta te który która "
        "które przy po być może musi ich jego jej tym tych także albo jeżeli gdy"
    ),
    "en": _words(
        "the and of to in is are for that with as by be on or an this which at from it must "
        "may not their its has have shall when within"
    ),
}
_WORD = re.compile(r"\w+", re.UNICODE)


def language_of(text: str) -> str | None:
    """`pl` or `en` by which language's common words the text uses more; None if neither."""
    words = [word.lower() for word in _WORD.findall(text)]
    counts = {
        language: sum(word in stop for word in words) for language, stop in _STOP_WORDS.items()
    }
    best = max(counts, key=lambda language: counts[language])
    if counts[best] == 0 or list(counts.values()).count(counts[best]) > 1:
        return None
    return best


def score_answers(cases: Sequence[AnswerCase], results: Mapping[str, ChatResult]) -> AnswerMetrics:
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
    )


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
    lines += ["", "Missed cases:", ""]
    lines += [f"- {case}: {reason}" for case, reason in metrics.missed.items()] or ["- none"]
    lines += ["", "Run:", ""]
    lines += [f"- {name}: {value}" for name, value in metadata.items()]
    return "\n".join(lines) + "\n"


def _share(count: int, total: int) -> float | None:
    return count / total if total else None
