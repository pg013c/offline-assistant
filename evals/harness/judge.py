"""The judge (ADR 0022): a local model that grades answers against reference key points.

It is called by the evaluation only, through the OpenAI-compatible API of the llama-server
that `make judge` starts, with a JSON schema and at temperature 0.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import httpx

JUDGE_PROMPT = (Path(__file__).parents[1] / "prompts" / "judge.md").read_text(encoding="utf-8")
JUDGE_MODEL = "qwen3-30b-a3b"
TIMEOUT_SECONDS = 120
MAX_TOKENS = 1024
_CORRECTNESS = ("correct", "partial", "wrong")
_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correctness": {"type": "string", "enum": list(_CORRECTNESS)},
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
    "required": ["correctness", "reason", "sentences"],
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
    key_points = "\n".join(f"- {point}" for point in judged.key_points)
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
        correctness = reply["correctness"]
        supported = {int(item["index"]): bool(item["supported"]) for item in reply["sentences"]}
        reason = str(reply["reason"])
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise _Invalid from error
    if correctness not in _CORRECTNESS:
        raise _Invalid
    cited = {sentence.index for sentence in judged.sentences if sentence.cites}
    if not cited <= set(supported):
        raise _Invalid
    return Verdict(
        correctness=cast(Literal["correct", "partial", "wrong"], correctness),
        reason=reason,
        supported={index: supported[index] for index in sorted(cited)},
    )
