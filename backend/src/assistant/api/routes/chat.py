from collections.abc import AsyncIterable
from typing import Annotated, assert_never

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse

from assistant.api.dependencies import get_answers
from assistant.api.schemas import (
    ChatCitationEvent,
    ChatDiscardEvent,
    ChatEndEvent,
    ChatErrorEvent,
    ChatEvent,
    ChatRequest,
    ChatTextEvent,
    ChatToolEvent,
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
    NoteSaved,
    ToolUsed,
)
from assistant.services.questions import Answerer

router = APIRouter(prefix="/chat", tags=["chat"])

Answers = Annotated[Answerer, Depends(get_answers)]


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
                            tool_turns=usage.tool_turns,
                        )
                        if usage
                        else None
                    ),
                )
            )
        case ToolUsed(name=name, arguments=arguments):
            return ChatEvent(ChatToolEvent(type="tool", name=name, arguments=arguments))
        case NoteSaved():
            # F-07a step 5 puts saved notes on the stream.
            raise NotImplementedError
        case _:
            assert_never(event)


@router.post("", response_class=EventSourceResponse)
async def ask_question(request: ChatRequest, answers: Answers) -> AsyncIterable[ChatEvent]:
    """Answer a question from the uploaded documents as Server-Sent Events."""
    async for event in answers.ask(request.question):
        yield _to_schema(event)
