import asyncio
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
# Candidates fetched before the similarity filter, so weak hits do not crowd out good ones.
CANDIDATES = 10


class QuestionService:
    """Answers a question from the indexed documents, as a stream of events."""

    def __init__(
        self,
        index: ChunkIndex,
        model: ChatModel,
        store: DocumentStore,
        min_similarity: float,
    ) -> None:
        """`min_similarity` is the dense similarity a passage needs to be used (F-03).

        A passage ranked first only for an exact term, but below it, is not used either: the
        answer would rest on a word, not on the meaning. F-04 measures this choice.
        """
        self._min_similarity = min_similarity
        self._index = index
        self._model = model
        self._store = store

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Text pieces, then citations, then an end event; or a no-passage notice."""
        # Embedding the question and querying the index block; keep them off the event loop.
        found = await asyncio.to_thread(self._index.search, question, CANDIDATES)
        results = [result for result in found if result.similarity >= self._min_similarity][
            :PASSAGES_PER_ANSWER
        ]
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
