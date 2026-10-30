"""Request and response models of the HTTP API. Services never return these (PY-12)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, RootModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    # True in comparison mode, which may use the network (ADR 0004); the UI shows it.
    network: bool


class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    status: Literal["processing", "ready", "failed"]
    chunk_count: int
    # None for formats without pages, such as text and Word files.
    page_count: int | None
    # Why parsing failed, for documents with status `failed`.
    failure_reason: str | None


class ErrorDetail(BaseModel):
    """One problem with one field of a request."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """The body of every error the API reports (PY-22)."""

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # A model from GET /api/models; the default when left out (F-08).
    model: str | None = None


class ModelChoiceResponse(BaseModel):
    """A model the API can answer with now."""

    id: str
    is_test_model: bool
    is_default: bool


class ChunkSummary(BaseModel):
    """A passage of a document: its id and where it is, without its text."""

    chunk_id: str
    position: int
    location: "CitationLocation"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    # Reranked or hybrid order; by default whatever the server is configured for (F-05).
    rerank: bool | None = None


class SearchHit(BaseModel):
    """A passage found for a query; `similarity` is the dense cosine similarity (0 to 1).

    `rerank_score` is the reranker's score (0 to 1) when the hits were reranked, else null.
    """

    chunk_id: str
    document_id: str
    document_title: str
    location: "CitationLocation"
    text: str
    similarity: float
    rerank_score: float | None


class ChatToolEvent(BaseModel):
    """The agent called a tool, with its arguments; sent before the answer text (F-07)."""

    type: Literal["tool"]
    name: str
    arguments: dict[str, Any]


class ChatNoteEvent(BaseModel):
    """The agent saved a note for the user (F-07a)."""

    type: Literal["note"]
    id: str
    title: str


class ChatTextEvent(BaseModel):
    """A piece of the answer text, in order."""

    type: Literal["text"]
    text: str


class CitationLocation(BaseModel):
    """Where the cited passage is; parts the document does not have are empty."""

    heading_path: list[str]
    article: str | None
    paragraph: str | None
    page: int | None


class ChatCitationEvent(BaseModel):
    """A passage the answer is based on, quoted verbatim."""

    type: Literal["citation"]
    # The passage number the answer's markers use for this citation, e.g. 2 for "[2]".
    number: int
    chunk_id: str
    document_id: str
    document_title: str
    quote: str
    location: CitationLocation


class ChatDiscardEvent(BaseModel):
    """The text sent since the last discard (or the start) is void; the retry's text follows."""

    type: Literal["discard"]
    reason: str


class ChatErrorEvent(BaseModel):
    """The model gave no valid answer; an end event still follows."""

    type: Literal["error"]
    code: Literal["invalid_answer", "model_unreachable", "model_timeout", "model_error"]
    message: str


class ChatUsage(BaseModel):
    """What the answer cost: tokens over every attempt, and its timings in milliseconds."""

    prompt_tokens: int
    completion_tokens: int
    first_token_ms: float | None
    total_ms: float
    attempts: int
    # Model turns that called tools before the answer.
    tool_turns: int


class ChatEndEvent(BaseModel):
    """The last event of an answer; `usage` is null when no model answered."""

    type: Literal["end"]
    model_id: str
    found: bool
    is_test_model: bool
    usage: ChatUsage | None


class ChatEvent(
    RootModel[
        Annotated[
            ChatToolEvent
            | ChatNoteEvent
            | ChatTextEvent
            | ChatDiscardEvent
            | ChatErrorEvent
            | ChatCitationEvent
            | ChatEndEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One event of a streamed answer: tool, note, text, discard, error, citation or end."""


class NoteSummary(BaseModel):
    """A note the agent saved, as listed."""

    id: str
    title: str
    created: datetime


class NoteSourceResponse(BaseModel):
    """A passage a note cites, by the number its markers use."""

    number: int
    document_title: str
    chunk_id: str
    location: CitationLocation


class NoteDetail(NoteSummary):
    """A note with its content, its sources and the Markdown file's text."""

    content: str
    sources: list[NoteSourceResponse]
    markdown: str
