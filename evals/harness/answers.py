"""The answer suite (F-06): what /api/chat streamed for each case, and its metrics."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


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
    values: dict[str, float | None]
    cases: dict[str, int]
    performance: dict[str, float | None]
    missed: dict[str, str] = field(default_factory=dict)


def parse_chat_stream(text: str) -> ChatResult:
    raise NotImplementedError


def language_of(text: str) -> str | None:
    raise NotImplementedError


def score_answers(cases: Sequence[AnswerCase], results: Mapping[str, ChatResult]) -> AnswerMetrics:
    raise NotImplementedError


def answers_markdown(metrics: AnswerMetrics, metadata: Mapping[str, Any]) -> str:
    raise NotImplementedError
