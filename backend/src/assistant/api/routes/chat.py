from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse

from assistant.api.dependencies import get_question_service
from assistant.api.schemas import (
    ChatCitationEvent,
    ChatEndEvent,
    ChatEvent,
    ChatRequest,
    ChatTextEvent,
)
from assistant.domain.answers import AnswerCitation, AnswerEvent, AnswerText
from assistant.services.questions import QuestionService

router = APIRouter(prefix="/chat", tags=["chat"])

Questions = Annotated[QuestionService, Depends(get_question_service)]


def _to_schema(event: AnswerEvent) -> ChatEvent:
    match event:
        case AnswerText(text=text):
            return ChatTextEvent(type="text", text=text)
        case AnswerCitation(citation=citation):
            return ChatCitationEvent(
                type="citation",
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                document_title=citation.document_title,
                quote=citation.quote,
            )
        case _:
            return ChatEndEvent(type="end", model_id=event.model_id, found=event.found)


@router.post("", response_class=EventSourceResponse)
async def ask_question(request: ChatRequest, questions: Questions) -> AsyncIterable[ChatEvent]:
    """Answer a question from the uploaded documents as Server-Sent Events."""
    async for event in questions.ask(request.question):
        yield _to_schema(event)
