from assistant.adapters.qdrant_chunk_index import best_first
from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ScoredChunk


def hit(position: int, score: float, similarity: float) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(id=f"doc:{position}", document_id="doc", position=position, text="..."),
        score=score,
        similarity=similarity,
    )


def test_a_higher_fused_score_comes_first() -> None:
    results = [hit(0, 0.3, 0.9), hit(1, 0.8, 0.4)]

    assert [r.chunk.id for r in best_first(results)] == ["doc:1", "doc:0"]


def test_a_tie_in_the_fused_ranking_goes_to_the_closer_meaning() -> None:
    # Dense first and keyword second ties with keyword first and dense second.
    results = [hit(4, 0.8333, 0.681), hit(2, 0.8333, 0.770)]

    assert [r.chunk.id for r in best_first(results)] == ["doc:2", "doc:4"]


def test_a_full_tie_keeps_document_order() -> None:
    results = [hit(5, 0.5, 0.5), hit(3, 0.5, 0.5)]

    assert [r.chunk.id for r in best_first(results)] == ["doc:3", "doc:5"]
