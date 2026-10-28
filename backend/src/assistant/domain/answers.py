"""What a streamed answer is made of."""

import re
from dataclasses import dataclass

NO_RELEVANT_PASSAGE = "No relevant passage was found in the uploaded documents."
QUOTE_SENTENCES = 2
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    document_id: str
    document_title: str
    quote: str


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
