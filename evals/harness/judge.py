"""The judge (ADR 0022): a local model that grades answers against reference key points.

It is called by the evaluation only, through the OpenAI-compatible API of the llama-server
that `make judge` starts, with a JSON schema and at temperature 0.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

JUDGE_PROMPT = (Path(__file__).parents[1] / "prompts" / "judge.md").read_text(encoding="utf-8")
JUDGE_MODEL = "qwen3-30b-a3b"
TIMEOUT_SECONDS = 600
MAX_TOKENS = 8192
_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "made": {"type": "boolean"}},
                "required": ["index", "made"],
            },
        },
        "reason": {"type": "string"},
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "supported": {"type": "boolean"}},
                "required": ["index", "supported"],
            },
        },
    },
    "required": ["key_points", "reason", "sentences"],
}


class JudgeUnavailable(Exception):
    """The judge server does not answer."""


@dataclass(frozen=True)
class JudgedSentence:
    """A sentence of the answer, numbered from 1, with the passage numbers it cites."""

    index: int
    text: str
    cites: tuple[int, ...]


@dataclass(frozen=True)
class JudgeInput:
    question: str
    key_points: tuple[str, ...]
    answer: str
    sentences: tuple[JudgedSentence, ...]
    # Passage number -> the passage's text.
    passages: Mapping[int, str]


@dataclass(frozen=True)
class Verdict:
    correctness: Literal["correct", "partial", "wrong"]
    reason: str
    # Sentence index -> whether its cited passages support it; cited sentences only.
    supported: Mapping[int, bool]
    # Key point index (from 1) -> whether the answer makes it; correctness follows from these.
    made: Mapping[int, bool] = field(default_factory=dict)


class _Invalid(Exception):
    """The judge's reply is not a verdict for this input."""


class JudgeClient:
    """Asks the judge for a verdict; an unreadable reply is retried, then not judged."""

    def __init__(self, url: str, http: httpx.Client | None = None, max_retries: int = 2) -> None:
        self._url = url
        self._http = http or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._max_retries = max_retries

    def judge(self, judged: JudgeInput) -> Verdict | None:
        body = {
            "model": JUDGE_MODEL,
            "messages": [
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": _user_message(judged)},
            ],
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "verdict", "strict": True, "schema": _SCHEMA},
            },
        }
        for _ in range(self._max_retries + 1):
            try:
                response = self._http.post(f"{self._url}/v1/chat/completions", json=body)
            except httpx.TransportError as error:
                raise JudgeUnavailable(
                    f"No judge answers at {self._url}. Start it with: make judge"
                ) from error
            try:
                return _verdict(response, judged)
            except _Invalid:
                continue
        return None


def _user_message(judged: JudgeInput) -> str:
    key_points = "\n".join(f"{index}. {point}" for index, point in enumerate(judged.key_points, 1))
    sentences = "\n".join(f"{sentence.index}. {sentence.text}" for sentence in judged.sentences)
    passages = "\n\n".join(f"[{number}] {text}" for number, text in sorted(judged.passages.items()))
    return (
        f"Question: {judged.question}\n\nKey points:\n{key_points}\n\n"
        f"Answer, by sentence:\n{sentences}\n\nCited passages:\n{passages or '(none)'}"
    )


def _verdict(response: httpx.Response, judged: JudgeInput) -> Verdict:
    try:
        content = response.json()["choices"][0]["message"]["content"]
        reply = json.loads(content)
        made = {int(item["index"]): bool(item["made"]) for item in reply["key_points"]}
        supported = {int(item["index"]): bool(item["supported"]) for item in reply["sentences"]}
        reason = str(reply["reason"])
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise _Invalid from error
    points = range(1, len(judged.key_points) + 1)
    if not set(points) <= set(made):
        raise _Invalid
    cited = {sentence.index for sentence in judged.sentences if sentence.cites}
    if not cited <= set(supported):
        raise _Invalid
    made = {index: made[index] for index in points}
    return Verdict(
        correctness=_correctness(made),
        reason=reason,
        supported={index: supported[index] for index in sorted(cited)},
        made=made,
    )


def _correctness(made: Mapping[int, bool]) -> Literal["correct", "partial", "wrong"]:
    """All key points made is correct, none is wrong, the rest is partial."""
    if all(made.values()):
        return "correct"
    if any(made.values()):
        return "partial"
    return "wrong"
