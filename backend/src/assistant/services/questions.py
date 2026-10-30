import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

import structlog

from assistant.domain.answers import (
    NO_RELEVANT_PASSAGE,
    AnswerCitation,
    AnswerDiscarded,
    Answered,
    AnswerEnd,
    AnswerEvent,
    AnswerFailed,
    AnswerText,
    AttemptDiscarded,
    Citation,
    ModelFailed,
    TextDelta,
    Usage,
    quote_from,
)
from assistant.domain.documents import Chunk, indexed_text
from assistant.domain.errors import RerankerOff
from assistant.domain.ranking import rerank as by_score
from assistant.ports.chat_model import ChatModel
from assistant.ports.chunk_index import ChunkIndex, ScoredChunk
from assistant.ports.document_store import DocumentStore
from assistant.ports.reranker import Reranker

log = structlog.get_logger(__name__)

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

    @property
    def min_similarity(self) -> float:
        return self._min_similarity

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
        # The threshold applies to the best ten in either order, the hits the evaluation sees.
        found = await asyncio.to_thread(self._find, question, CANDIDATES, None)
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
        usage: Usage | None = None
        outcome = "no_outcome"
        covered = True
        async for event in self._model.answer(question, passages):
            match event:
                case TextDelta(text=text):
                    yield AnswerText(text=text)
                case AttemptDiscarded(reason=reason):
                    yield AnswerDiscarded(reason=reason)
                case ModelFailed(code=code, detail=detail, usage=usage):
                    yield AnswerFailed(code=code, message=detail)
                    outcome = code
                case Answered(answer=answer, usage=usage):
                    outcome = "answered" if answer.covered else "not_covered"
                    covered = answer.covered
                    # The passages the model says the answer rests on, in its order (AI-01).
                    for number in dict.fromkeys(answer.cited):
                        yield AnswerCitation(citation=self._citation(passages[number - 1]))
        _log_model_call(self._model.model_id, outcome, len(passages), usage)
        yield AnswerEnd(
            model_id=self._model.model_id,
            found=covered,
            is_test_model=self._model.is_test_model,
            usage=usage,
        )

    def _citation(self, chunk: Chunk) -> Citation:
        document = self._store.get(chunk.document_id)
        return Citation(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=document.title if document else chunk.document_id,
            quote=quote_from(chunk.text),
            location=chunk.location,
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


def _log_model_call(model_id: str, outcome: str, passages: int, usage: Usage | None) -> None:
    """One info line per answer from a model: ids, timings and tokens, never text (AI-53, AI-60)."""
    fields = (
        {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "first_token_ms": usage.first_token_ms,
            "total_ms": usage.total_ms,
            "attempts": usage.attempts,
        }
        if usage
        else {}
    )
    log.info("model_answered", model_id=model_id, outcome=outcome, passages=passages, **fields)
