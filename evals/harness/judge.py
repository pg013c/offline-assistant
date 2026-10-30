"""The judge (ADR 0022): a local model that grades answers against reference key points."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import httpx

JUDGE_PROMPT = ""


class JudgeUnavailable(Exception):
    """The judge server does not answer."""


@dataclass(frozen=True)
class JudgedSentence:
    index: int
    text: str
    cites: tuple[int, ...]


@dataclass(frozen=True)
class JudgeInput:
    question: str
    key_points: tuple[str, ...]
    answer: str
    sentences: tuple[JudgedSentence, ...]
    passages: Mapping[int, str]


@dataclass(frozen=True)
class Verdict:
    correctness: Literal["correct", "partial", "wrong"]
    reason: str
    supported: Mapping[int, bool]


class JudgeClient:
    def __init__(self, url: str, http: httpx.Client | None = None, max_retries: int = 2) -> None:
        raise NotImplementedError

    def judge(self, judged: JudgeInput) -> Verdict | None:
        raise NotImplementedError
