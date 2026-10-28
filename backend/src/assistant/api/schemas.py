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
    chunk_count: int


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


class ChatTextEvent(BaseModel):
    """A piece of the answer text, in order."""

    type: Literal["text"]
    text: str


class ChatCitationEvent(BaseModel):
    """A passage the answer is based on, quoted verbatim."""

    type: Literal["citation"]
    chunk_id: str
    document_id: str
    document_title: str
    quote: str


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
