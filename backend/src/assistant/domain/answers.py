"""What a streamed answer is made of."""

from dataclasses import dataclass

NO_RELEVANT_PASSAGE = "No relevant passage was found in the uploaded documents."


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


type AnswerEvent = AnswerText | AnswerCitation | AnswerEnd
