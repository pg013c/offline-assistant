"""What a streamed answer is made of."""

import re
from dataclasses import dataclass, field
from typing import Any

from assistant.domain.documents import ChunkLocation

NO_RELEVANT_PASSAGE = "No relevant passage was found in the uploaded documents."
QUOTE_SENTENCES = 2
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    document_id: str
    document_title: str
    quote: str
    location: ChunkLocation = field(default_factory=ChunkLocation)


@dataclass(frozen=True, slots=True)
class AnswerText:
    text: str


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    citation: Citation


@dataclass(frozen=True, slots=True)
class AnswerEnd:
    model_id: str
    found: bool
    is_test_model: bool


type AnswerEvent = AnswerText | AnswerCitation | AnswerEnd

# The structured answer a language model is asked for (FR-13, AI-20): the answer first, so it
# can stream, then the numbers of the passages it rests on, counted from 1.
ANSWER_SCHEMA: dict[str, Any] = {}


class InvalidAnswer(Exception):
    """The model's output is not a valid answer; the reason is fed back to it (AI-21)."""


@dataclass(frozen=True, slots=True)
class ModelAnswer:
    text: str
    cited: tuple[int, ...]


def parse_answer(raw: str, passage_count: int) -> ModelAnswer:
    """The validated answer, or `InvalidAnswer` saying what to correct."""
    raise NotImplementedError


class AnswerTextExtractor:
    """Pulls the answer text out of the structured answer while it is being written."""

    def feed(self, chunk: str) -> str:
        """The answer text decoded from this chunk; empty before and after the answer."""
        raise NotImplementedError


def opening_sentences(text: str, count: int = QUOTE_SENTENCES) -> str:
    """The first `count` sentences of the text, copied verbatim."""
    stripped = text.strip()
    boundaries = [match.start() for match in _SENTENCE_END.finditer(stripped)]
    if len(boundaries) < count:
        return stripped
    return stripped[: boundaries[count - 1]]


def quote_from(text: str) -> str:
    """The quote shown for a cited chunk, copied verbatim (AI-03)."""
    return opening_sentences(text)
