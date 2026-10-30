"""The agent: it looks passages up with tools, then answers from them (F-07, FR-10)."""

from collections.abc import AsyncIterator

from assistant.domain.answers import AnswerEvent
from assistant.ports.chat_model import ToolCallingModel
from assistant.ports.document_store import DocumentStore
from assistant.services.questions import QuestionService


class AgentService:
    def __init__(
        self,
        questions: QuestionService,
        model: ToolCallingModel,
        store: DocumentStore,
        max_tool_turns: int,
    ) -> None:
        raise NotImplementedError

    def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        raise NotImplementedError
