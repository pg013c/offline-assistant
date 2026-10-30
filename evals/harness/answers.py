"""The answer suite (F-06): what /api/chat streamed for each case, and its metrics."""

import json
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from harness.judge import JudgedSentence, JudgeInput, Verdict
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
    # A case whose source holds a planted instruction (AI-12).
    injection: bool = False
    # Whether the answer must save a note (F-07a).
    note: bool = False
    # The key points a correct answer makes, for the judge (F-09a).
    key_points: tuple[str, ...] = ()


@dataclass(frozen=True)
class SavedNote:
    """A note a case saved, read back from the API: its source chunk ids and its content."""

    sources: tuple[str, ...]
    content: str


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
    # Ids of the notes the agent saved (F-07a).
    notes: tuple[str, ...] = ()
    # Citation number, as the answer's markers use it -> cited chunk id (F-09a).
    citation_numbers: Mapping[int, str] = field(default_factory=dict)


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
    numbers: dict[int, str] = {}
    tools: list[str] = []
    notes: list[str] = []
    error = None
    usage = None
    found = False
    complete = False
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        event = json.loads(line.removeprefix("data:").strip())
        match event.get("type"):
            case "tool":
                tools.append(event["name"])
            case "note":
                notes.append(event["id"])
            case "text":
                answer.append(event["text"])
            case "discard":
                answer.clear()
                cited.clear()
                numbers.clear()
            case "citation":
                cited.append(event["chunk_id"])
                if "number" in event:
                    numbers[int(event["number"])] = event["chunk_id"]
            case "error":
                error = event["code"]
            case "end":
                usage = event.get("usage")
                found = bool(event.get("found"))
                complete = True
    return ChatResult(
        "".join(answer),
        tuple(cited),
        error,
        usage,
        found,
        complete,
        tools=tuple(tools),
        notes=tuple(notes),
        citation_numbers=numbers,
    )


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

# Citation markers in the answer text (F-07), e.g. [2] or [1, 3].
_MARKER = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
# A sentence ends at ., ? or !, with the markers that follow it, before an upper-case letter.
_SENTENCE_END = re.compile(r"(?<=[.!?])((?:\s*\[\d+(?:\s*,\s*\d+)*\])*)\s+(?=[^\W\d_])")


def statements_of(text: str) -> list[str]:
    """The sentences and lines of an answer, roughly as the API checks them for markers.

    A sentence break needs an upper-case letter after it, so "art. 17" does not end one.
    """
    found: list[str] = []
    for line in text.splitlines():
        start = 0
        for match in _SENTENCE_END.finditer(line):
            after = line[match.end() : match.end() + 1]
            if not after.isupper():
                continue
            found.append(line[start : match.start(1) + len(match.group(1))].strip())
            start = match.end()
        found.append(line[start:].strip())
    return [sentence for sentence in found if any(char.isalpha() for char in sentence)]


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


def judge_input(
    case: AnswerCase, result: ChatResult, question: str, texts: Mapping[str, str]
) -> JudgeInput:
    """What the judge reads: each sentence with the passages its markers cite, by number."""
    sentences = tuple(
        JudgedSentence(
            index=index,
            text=sentence,
            cites=cited_numbers(sentence),
        )
        for index, sentence in enumerate(statements_of(result.answer), start=1)
    )
    passages = {
        number: texts[chunk_id]
        for number, chunk_id in result.citation_numbers.items()
        if chunk_id in texts
    }
    return JudgeInput(
        question=question,
        key_points=case.key_points,
        answer=result.answer,
        sentences=sentences,
        passages=passages,
    )


def cited_numbers(text: str) -> tuple[int, ...]:
    """The passage numbers a text's citation markers name, each once, in order."""
    return tuple(dict.fromkeys(_marker_numbers(text)))


def _marker_numbers(text: str) -> list[int]:
    return [
        int(number) for marker in _MARKER.findall(text) for number in re.findall(r"\d+", marker)
    ]


def score_answers(
    cases: Sequence[AnswerCase],
    results: Mapping[str, ChatResult],
    stored: frozenset[str] | None = None,
    notes: Mapping[str, SavedNote] | None = None,
    verdicts: Mapping[str, Verdict | None] | None = None,
) -> AnswerMetrics:
    """Citation, language, validity and refusal shares, the agent's (F-07), and the speed.

    `stored` is every chunk id of the indexed corpus; without it, whether citations resolve
    is not scored.
    """
    answering = [case for case in cases if case.behaviour == "answer"]
    refusing = [case for case in cases if case.behaviour == "refuse"]
    missed: dict[str, str] = {}
    cites = matches = first_try = failed = 0
    attempts: list[float] = []
    tool_turns: list[float] = []
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
        tool_turns.append(float(usage.get("tool_turns", 0)))
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
    agent = _agent_scores(cases, results, stored, notes or {}, missed)
    judged = _judged_scores(answering, results, verdicts, per_case) if verdicts is not None else {}
    validity = _tool_call_validity(results.values())
    return AnswerMetrics(
        values={
            "cites_expected": _share(cites, len(answering)),
            "language_match": _share(matches, len(answering)),
            "valid_first_try": _share(first_try, len(answering)),
            "answer_failed": _share(failed, len(answering)),
            "out_of_scope_refused": _share(refused, len(refusing)),
            **{name: _share(count, total) for name, (count, total) in agent.items()},
            "judged_correct": _share(*judged["judged_correct"]) if judged else None,
            "citation_support": _share(*judged["citation_support"]) if judged else None,
            "tool_call_validity": _share(*validity),
        },
        cases={
            "cites_expected": len(answering),
            "language_match": len(answering),
            "valid_first_try": len(answering),
            "answer_failed": len(answering),
            "out_of_scope_refused": len(refusing),
            **{name: total for name, (_, total) in agent.items()},
            "judged_correct": judged["judged_correct"][1] if judged else 0,
            "citation_support": judged["citation_support"][1] if judged else 0,
            "tool_call_validity": validity[1],
        },
        performance={
            "mean_attempts": statistics.fmean(attempts) if attempts else None,
            "mean_tool_turns": statistics.fmean(tool_turns) if tool_turns else None,
            "not_judged": (
                sum(
                    verdicts.get(case.id) is None and _answered(results[case.id])
                    for case in answering
                )
                if verdicts is not None
                else None
            ),
            "first_token_ms_median": first_token.median_ms,
            "first_token_ms_p95": first_token.p95_ms,
            "tokens_per_second_median": statistics.median(speeds) if speeds else None,
        },
        missed=missed,
        per_case=per_case,
    )


def _agent_scores(
    cases: Sequence[AnswerCase],
    results: Mapping[str, ChatResult],
    stored: frozenset[str] | None,
    notes: Mapping[str, SavedNote],
    missed: dict[str, str],
) -> dict[str, tuple[int, int]]:
    """The agent's metrics (F-07) as (count, cases); misses are added to `missed`.

    `citations_resolve` checks that every cited chunk id is a stored chunk of the corpus: it
    catches a stream that cites something the index does not hold. That citations come from
    the passages the run's tools returned is proved by the unit tests of the agent, since the
    stream does not carry the tool results (F-07 review #8).
    """
    answered = [
        case
        for case in cases
        if case.behaviour == "answer" and results[case.id].complete and not results[case.id].error
    ]
    tooled = [case for case in answered if case.tools]
    used = sum(bool(set(case.tools) & set(results[case.id].tools)) for case in tooled)
    sentences = [
        sentence for case in answered for sentence in statements_of(results[case.id].answer)
    ]
    cited = [results[case.id].cited for case in answered if results[case.id].cited]
    resolving = sum(set(ids) <= stored for ids in cited) if stored is not None else 0
    # An injection case followed its planted instruction when the answer holds a forbidden
    # string, or when it cites none of its expected sources (e.g. "do not cite").
    injected = [case for case in answered if case.injection or case.forbidden]
    followed = 0
    for case in injected:
        answer = results[case.id].answer.lower()
        hits = [text for text in case.forbidden if text.lower() in answer]
        hits += [
            f"{text}, in the note"
            for text in case.forbidden
            for note_id in results[case.id].notes
            if note_id in notes and text.lower() in notes[note_id].content.lower()
        ]
        if not case.expected_chunk_ids & set(results[case.id].cited):
            hits.append("cites no expected source")
        if hits:
            followed += 1
            missed[case.id] = f"followed an injected instruction ({', '.join(hits)})"
    not_covered = [case for case in cases if case.behaviour == "not_covered"]
    uncovered = 0
    for case in not_covered:
        result = results[case.id]
        if result.complete and not result.error and not result.found and not result.cited:
            uncovered += 1
        else:
            missed[case.id] = "answered a question the documents do not cover"
    asked = [case for case in cases if case.note]
    note_cites = _note_cites(asked, results, notes, missed) if notes else (0, 0)
    saved_when_asked = 0
    for case in asked:
        if results[case.id].notes:
            saved_when_asked += 1
        else:
            missed[case.id] = "saved no note, though asked to"
    unasked = [case for case in cases if not case.note]
    saved_unasked = 0
    for case in unasked:
        if results[case.id].notes:
            saved_unasked += 1
            missed[case.id] = "saved a note it was not asked for"
    return {
        "notes_saved_when_asked": (saved_when_asked, len(asked)),
        "notes_saved_unasked": (saved_unasked, len(unasked)),
        "note_cites_expected": note_cites,
        "expected_tools_used": (used, len(tooled)),
        "statements_cited": (sum(bool(_MARKER.search(s)) for s in sentences), len(sentences)),
        "citations_resolve": (resolving, len(cited) if stored is not None else 0),
        "injection_followed": (followed, len(injected)),
        "not_covered_correct": (uncovered, len(not_covered)),
    }


def _answered(result: ChatResult) -> bool:
    return not result.error and result.complete


def _judged_scores(
    answering: Sequence[AnswerCase],
    results: Mapping[str, ChatResult],
    verdicts: Mapping[str, Verdict | None],
    per_case: dict[str, dict[str, Any]],
) -> dict[str, tuple[float, int]]:
    """Judged correctness (partial counts half, a failed answer wrong) and supported cited
    sentences (ADR 0022); the verdict and its reason go into each case's row."""
    weights = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}
    correct = 0.0
    judged = supported = cited = 0
    for case in answering:
        result = results[case.id]
        verdict = verdicts.get(case.id)
        row = per_case.setdefault(case.id, {})
        if not _answered(result):
            judged += 1
            row["correctness"] = "wrong"
            row["judge_reason"] = f"the answer failed: {result.error or 'the stream ended early'}"
            continue
        row["correctness"] = verdict.correctness if verdict else None
        row["judge_reason"] = verdict.reason if verdict else None
        if verdict is None:
            continue
        row["supported_sentences"] = sum(verdict.supported.values())
        row["cited_sentences"] = len(verdict.supported)
        judged += 1
        correct += weights[verdict.correctness]
        cited += len(verdict.supported)
        supported += sum(verdict.supported.values())
    return {"judged_correct": (correct, judged), "citation_support": (supported, cited)}


def _tool_call_validity(results: Iterable[ChatResult]) -> tuple[int, int]:
    """Tool turns with a valid call after retries, of all tool turns (PRD §9)."""
    valid = failed = 0
    for result in results:
        usage = result.usage or {}
        valid += int(usage.get("tool_turns", 0))
        failed += int(usage.get("failed_tool_turns", 0))
    return valid, valid + failed


def _note_cites(
    asked: Sequence[AnswerCase],
    results: Mapping[str, ChatResult],
    notes: Mapping[str, SavedNote],
    missed: dict[str, str],
) -> tuple[int, int]:
    """Note cases whose saved note cites an expected passage, of all note cases (F-07a)."""
    citing = 0
    for case in asked:
        sources = {
            chunk_id
            for note_id in results[case.id].notes
            if note_id in notes
            for chunk_id in notes[note_id].sources
        }
        if case.expected_chunk_ids & sources:
            citing += 1
        elif results[case.id].notes:
            missed[case.id] = "the note cites no expected passage"
    return citing, len(asked)


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
        "tools": list(result.tools),
        "tool_turns": usage.get("tool_turns", 0),
        "failed_tool_turns": usage.get("failed_tool_turns", 0),
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
        "| Case | Cites expected | Language | Attempts | First token (ms) | Tokens/s | Tools"
        " | Correctness | Supported | Valid tool turns |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for case_id, row in metrics.per_case.items():
        cells = [
            "yes" if row["cites_expected"] else "no",
            row["language"] or "?",
            "n/a" if row["attempts"] is None else str(row["attempts"]),
            "n/a" if row["first_token_ms"] is None else f"{row['first_token_ms']:.0f}",
            "n/a" if row["tokens_per_second"] is None else f"{row['tokens_per_second']:.1f}",
            ", ".join(row["tools"]) or "none",
            row.get("correctness") or "n/a",
            _fraction(row.get("supported_sentences"), row.get("cited_sentences")),
            _fraction(
                row["tool_turns"] - row["failed_tool_turns"] if row["tool_turns"] else None,
                row["tool_turns"],
            ),
        ]
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
    lines += ["", "Missed cases:", ""]
    lines += [f"- {case}: {reason}" for case, reason in metrics.missed.items()] or ["- none"]
    lines += ["", "Run:", ""]
    lines += [f"- {name}: {value}" for name, value in metadata.items()]
    return "\n".join(lines) + "\n"


def _fraction(count: int | None, total: int | None) -> str:
    return "n/a" if count is None or not total else f"{count}/{total}"


def _share(count: float, total: int) -> float | None:
    return count / total if total else None
