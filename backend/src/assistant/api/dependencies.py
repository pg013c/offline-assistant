"""Services for route handlers. The composition root puts them on `app.state` (PY-21)."""

from typing import cast

from fastapi import Request

from assistant.services.documents import DocumentService
from assistant.services.notes import NoteService
from assistant.services.questions import Answerer, QuestionService


def get_document_service(request: Request) -> DocumentService:
    return cast(DocumentService, request.app.state.document_service)


def get_question_service(request: Request) -> QuestionService:
    return cast(QuestionService, request.app.state.question_service)


def get_answers(request: Request) -> Answerer:
    return cast(Answerer, request.app.state.answers)


def get_note_service(request: Request) -> NoteService:
    return cast(NoteService, request.app.state.note_service)
