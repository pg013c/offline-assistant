import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    AnswerEnd,
    AnswerEvent,
    AnswerText,
    Citation,
    quote_from,
)
from assistant.domain.documents import Chunk, indexed_text
from assistant.domain.errors import RerankerOff
from assistant.domain.ranking import rerank as by_score
from assistant.ports.chat_model import ChatModel
from assistant.ports.chunk_index import ChunkIndex, ScoredChunk
from assistant.ports.document_store import DocumentStore
from assistant.ports.reranker import Reranker

PASSAGES_PER_ANSWER = 3
# Candidates fetched before the similarity filter, so weak hits do not crowd out good ones.
CANDIDATES = 10
# Hybrid candidates the reranker scores (F-05).
RERANK_CANDIDATES = 30


@dataclass(frozen=True, slots=True)
class FoundPassage:
    """A passage found for a query, with its document's title."""

    chunk: Chunk
    document_title: str
    similarity: float
    rerank_score: float | None = None


class QuestionService:
    """Answers a question from the indexed documents, as a stream of events."""

    def __init__(
        self,
        index: ChunkIndex,
        model: ChatModel,
        store: DocumentStore,
        min_similarity: float,
        reranker: Reranker | None = None,
    ) -> None:
        """`min_similarity` is the dense similarity a passage needs to be used (F-03).

        A passage ranked first only for an exact term, but below it, is not used either: the
        answer would rest on a word, not on the meaning. F-04 measures this choice. With a
        `reranker`, candidates are reordered by it by default; the threshold still decides
        whether a passage is used (F-05).
        """
        self._min_similarity = min_similarity
        self._reranker = reranker
        self._index = index
        self._model = model
        self._store = store

    async def search(
        self, query: str, limit: int, rerank: bool | None = None
    ) -> list[FoundPassage]:
        """The best passages for the query, best first, without any threshold.

        `rerank` asks for the reranker's order or the index's; by default the reranker's
        when one is configured.
        """
        found = await asyncio.to_thread(self._find, query, limit, rerank)
        titles: dict[str, str] = {}
        for result, _ in found:
            document_id = result.chunk.document_id
            if document_id not in titles:
                document = self._store.get(document_id)
                titles[document_id] = document.title if document else document_id
        return [
            FoundPassage(
                chunk=result.chunk,
                document_title=titles[result.chunk.document_id],
                similarity=result.similarity,
                rerank_score=score,
            )
            for result, score in found
        ]

    async def ask(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Text pieces, then citations, then an end event; or a no-passage notice."""
        # Embedding the question and querying the index block; keep them off the event loop.
        # The threshold applies after reranking, to every candidate the reranker scored.
        candidates = RERANK_CANDIDATES if self._reranker else CANDIDATES
        found = await asyncio.to_thread(self._find, question, candidates, None)
        results = [result for result, _ in found if result.similarity >= self._min_similarity][
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

    def _find(
        self, query: str, limit: int, rerank: bool | None
    ) -> Sequence[tuple[ScoredChunk, float | None]]:
        """Up to `limit` candidates in the index's or the reranker's order, with its scores."""
        if rerank and self._reranker is None:
            raise RerankerOff
        reranker = self._reranker if rerank is not False else None
        if reranker is None:
            return [(result, None) for result in self._index.search(query, limit)]
        candidates = self._index.search(query, max(limit, RERANK_CANDIDATES))
        scores = reranker.score(query, [indexed_text(result.chunk) for result in candidates])
        return by_score(candidates, scores)[:limit]
