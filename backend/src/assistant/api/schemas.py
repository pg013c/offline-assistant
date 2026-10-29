"""Request and response models of the HTTP API. Services never return these (PY-12)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


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


class ChunkSummary(BaseModel):
    """A passage of a document: its id and where it is, without its text."""

    chunk_id: str
    position: int
    location: "CitationLocation"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    """A passage found for a query; `similarity` is the dense cosine similarity (0 to 1)."""

    chunk_id: str
    document_id: str
    document_title: str
    location: "CitationLocation"
    text: str
    similarity: float


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
    chunk_id: str
    document_id: str
    document_title: str
    quote: str
    location: CitationLocation


class ChatEndEvent(BaseModel):
    """The last event of an answer."""

    type: Literal["end"]
    model_id: str
    found: bool
    is_test_model: bool


class ChatEvent(
    RootModel[
        Annotated[ChatTextEvent | ChatCitationEvent | ChatEndEvent, Field(discriminator="type")]
    ]
):
    """One event of a streamed answer: text, citation or end."""
