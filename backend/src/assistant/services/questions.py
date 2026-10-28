from collections.abc import AsyncIterator

from assistant.domain.answers import AnswerEvent
from assistant.ports.chat_model import ChatModel
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_store import DocumentStore


class QuestionService:
    """Answers a question from the indexed documents, as a stream of events."""

    def __init__(self, index: ChunkIndex, model: ChatModel, store: DocumentStore) -> None:
        raise NotImplementedError

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Text pieces, then citations, then an end event; or a no-passage notice."""
        raise NotImplementedError
        yield
