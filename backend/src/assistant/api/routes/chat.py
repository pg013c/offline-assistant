from collections.abc import AsyncIterable
from typing import Annotated, assert_never

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse

from assistant.api.dependencies import get_question_service
from assistant.api.schemas import (
    ChatCitationEvent,
    ChatDiscardEvent,
    ChatEndEvent,
    ChatErrorEvent,
    ChatEvent,
    ChatRequest,
    ChatTextEvent,
    ChatUsage,
    CitationLocation,
)
from assistant.domain.answers import (
    AnswerCitation,
    AnswerDiscarded,
    AnswerEnd,
    AnswerEvent,
    AnswerFailed,
    AnswerText,
    ToolUsed,
)
from assistant.services.questions import QuestionService

router = APIRouter(prefix="/chat", tags=["chat"])

Questions = Annotated[QuestionService, Depends(get_question_service)]


def _to_schema(event: AnswerEvent) -> ChatEvent:
    match event:
        case AnswerText(text=text):
            return ChatEvent(ChatTextEvent(type="text", text=text))
        case AnswerCitation(citation=citation):
            return ChatEvent(
                ChatCitationEvent(
                    type="citation",
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    document_title=citation.document_title,
                    quote=citation.quote,
                    location=CitationLocation(
                        heading_path=list(citation.location.heading_path),
                        article=citation.location.article,
                        paragraph=citation.location.paragraph,
                        page=citation.location.page,
                    ),
                )
            )
        case AnswerDiscarded(reason=reason):
            return ChatEvent(ChatDiscardEvent(type="discard", reason=reason))
        case AnswerFailed(code=code, message=message):
            return ChatEvent(ChatErrorEvent(type="error", code=code, message=message))
        case AnswerEnd(model_id=model_id, found=found, is_test_model=is_test_model, usage=usage):
            return ChatEvent(
                ChatEndEvent(
                    type="end",
                    model_id=model_id,
                    found=found,
                    is_test_model=is_test_model,
                    usage=(
                        ChatUsage(
                            prompt_tokens=usage.prompt_tokens,
                            completion_tokens=usage.completion_tokens,
                            first_token_ms=usage.first_token_ms,
                            total_ms=usage.total_ms,
                            attempts=usage.attempts,
                        )
                        if usage
                        else None
                    ),
                )
            )
        case ToolUsed():
            # Step 5 of F-07 puts tool calls on the stream.
            raise NotImplementedError
        case _:
            assert_never(event)


@router.post("", response_class=EventSourceResponse)
async def ask_question(request: ChatRequest, questions: Questions) -> AsyncIterable[ChatEvent]:
    """Answer a question from the uploaded documents as Server-Sent Events."""
    async for event in questions.ask(request.question):
        yield _to_schema(event)
