from collections.abc import AsyncIterator

from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    AnswerEnd,
    AnswerEvent,
    AnswerText,
    Citation,
    quote_from,
)
from assistant.ports.chat_model import ChatModel
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_store import DocumentStore

PASSAGES_PER_ANSWER = 3


class QuestionService:
    """Answers a question from the indexed documents, as a stream of events."""

    def __init__(self, index: ChunkIndex, model: ChatModel, store: DocumentStore) -> None:
        self._index = index
        self._model = model
        self._store = store

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Text pieces, then citations, then an end event; or a no-passage notice."""
        results = self._index.search(question, limit=PASSAGES_PER_ANSWER)
        if not results:
            yield AnswerText(text=NO_RELEVANT_PASSAGE)
            yield AnswerEnd(model_id=self._model.model_id, found=False)
            return

        passages = [result.chunk for result in results]
        async for piece in self._model.stream_answer(question, passages):
            yield AnswerText(text=piece)

        # The answer is built from the best passage, so that is the one cited.
        best = passages[0]
        titles = {document.id: document.title for document in self._store.list_documents()}
        yield AnswerCitation(
            citation=Citation(
                chunk_id=best.id,
                document_id=best.document_id,
                document_title=titles.get(best.document_id, best.document_id),
                quote=quote_from(best.text),
            )
        )
        yield AnswerEnd(model_id=self._model.model_id, found=True)
