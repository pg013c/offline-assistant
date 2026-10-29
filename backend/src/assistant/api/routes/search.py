from typing import Annotated

from fastapi import APIRouter, Depends

from assistant.api.dependencies import get_question_service
from assistant.api.schemas import CitationLocation, SearchHit, SearchRequest
from assistant.services.questions import QuestionService

router = APIRouter(prefix="/search", tags=["search"])

Questions = Annotated[QuestionService, Depends(get_question_service)]


@router.post("")
async def search_passages(request: SearchRequest, questions: Questions) -> list[SearchHit]:
    """The best-matching passages for a query, best first, without a similarity threshold.

    Used by the evaluation harness and for debugging retrieval. Asking for reranking when
    the server has no reranker is a 409 `reranker_off`.
    """
    found = await questions.search(request.query, request.limit, request.rerank)
    return [
        SearchHit(
            chunk_id=passage.chunk.id,
            document_id=passage.chunk.document_id,
            document_title=passage.document_title,
            location=CitationLocation(
                heading_path=list(passage.chunk.location.heading_path),
                article=passage.chunk.location.article,
                paragraph=passage.chunk.location.paragraph,
                page=passage.chunk.location.page,
            ),
            text=passage.chunk.text,
            similarity=passage.similarity,
            rerank_score=passage.rerank_score,
        )
        for passage in found
    ]
