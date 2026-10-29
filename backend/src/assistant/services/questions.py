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
# Dense similarity a passage needs to be used (F-03); tuned on fixtures, measured in F-04.
MIN_SIMILARITY = 0.5


class QuestionService:
    """Answers a question from the indexed documents, as a stream of events."""

    def __init__(
        self,
        index: ChunkIndex,
        model: ChatModel,
        store: DocumentStore,
        min_similarity: float = MIN_SIMILARITY,
    ) -> None:
        self._min_similarity = min_similarity
        self._index = index
        self._model = model
        self._store = store

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Text pieces, then citations, then an end event; or a no-passage notice."""
        results = self._index.search(question, limit=PASSAGES_PER_ANSWER)
        if not results:
            yield AnswerText(text=NO_RELEVANT_PASSAGE)
            yield AnswerEnd(
                model_id=self._model.model_id,
                found=False,
                is_test_model=self._model.is_test_model,
            )
            return

        passages = [result.chunk for result in results]
        async for piece in self._model.stream_answer(question, passages):
            yield AnswerText(text=piece)

        # The answer is built from the best passage, so that is the one cited.
        best = passages[0]
        document = self._store.get(best.document_id)
        yield AnswerCitation(
            citation=Citation(
                chunk_id=best.id,
                document_id=best.document_id,
                document_title=document.title if document else best.document_id,
                quote=quote_from(best.text),
                location=best.location,
            )
        )
        yield AnswerEnd(
            model_id=self._model.model_id,
            found=True,
            is_test_model=self._model.is_test_model,
        )
