"""Services for route handlers. The composition root puts them on `app.state` (PY-21)."""

from dataclasses import dataclass
from typing import cast

from fastapi import Request

from assistant.api.schemas import ChatRequest
from assistant.services.documents import DocumentService
from assistant.services.models import ChatModels
from assistant.services.notes import NoteService
from assistant.services.questions import Answerer, QuestionService
from assistant.settings import Settings


def get_document_service(request: Request) -> DocumentService:
    return cast(DocumentService, request.app.state.document_service)


def get_question_service(request: Request) -> QuestionService:
    return cast(QuestionService, request.app.state.question_service)


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_models(request: Request) -> ChatModels:
    return cast(ChatModels, request.app.state.models)


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """A question and what answers it: its named model, or the default."""

    question: str
    answerer: Answerer


def get_chat_turn(request: ChatRequest, http: Request) -> ChatTurn:
    """Resolved before the stream starts, so an unknown model is an ordinary error (F-08)."""
    return ChatTurn(question=request.question, answerer=get_models(http).answerer(request.model))


def get_note_service(request: Request) -> NoteService:
    return cast(NoteService, request.app.state.note_service)
