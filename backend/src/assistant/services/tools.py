"""The tools the agent may call: search, one article, two articles side by side (F-07)."""

from assistant.domain.tools import PassageLedger, ToolCall, ToolSpec
from assistant.ports.document_store import DocumentStore
from assistant.services.questions import QuestionService

ARTICLE_CAP = 12
COMPARE_CAP = 6

TOOLS: tuple[ToolSpec, ...] = ()


class DocumentTools:
    def __init__(self, questions: QuestionService, store: DocumentStore) -> None:
        raise NotImplementedError

    async def run(self, call: ToolCall, ledger: PassageLedger) -> str:
        raise NotImplementedError
