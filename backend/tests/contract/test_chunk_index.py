"""Contract for the ChunkIndex port; every adapter must pass it."""

from collections.abc import Callable

import pytest

from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ChunkIndex

ADAPTERS: list[Callable[[], ChunkIndex]] = [InMemoryChunkIndex]


def chunk(position: int, text: str, document_id: str = "doc") -> Chunk:
    return Chunk(
        id=f"{document_id}:{position}", document_id=document_id, position=position, text=text
    )


@pytest.fixture(params=ADAPTERS, ids=lambda adapter: adapter.__name__)
def index(request: pytest.FixtureRequest) -> ChunkIndex:
    factory: Callable[[], ChunkIndex] = request.param
    return factory()


def test_the_chunk_closest_to_the_question_ranks_first(index: ChunkIndex) -> None:
    index.add(
        [
            chunk(0, "Authorities may inspect records on request."),
            chunk(1, "Providers keep logs for six months."),
            chunk(2, "Member states designate notified bodies."),
        ]
    )

    results = index.search("How long do providers keep logs?", limit=3)

    assert results[0].chunk.id == "doc:1"


def test_a_chunk_with_an_exact_term_of_the_question_ranks_first(index: ChunkIndex) -> None:
    index.add(
        [
            chunk(0, "High-risk systems in education and employment need human oversight."),
            chunk(1, "Annex III lists the areas: education, employment, migration."),
        ]
    )

    results = index.search("Which areas does Annex III list?", limit=2)

    assert results[0].chunk.id == "doc:1"


def test_results_carry_the_dense_similarity(index: ChunkIndex) -> None:
    index.add([chunk(0, "Providers keep logs for six months.")])

    [result] = index.search("Providers keep logs", limit=1)

    assert 0 < result.similarity <= 1
    assert result.chunk == chunk(0, "Providers keep logs for six months.")


def test_the_limit_is_respected(index: ChunkIndex) -> None:
    index.add([chunk(n, f"Providers keep logs, rule {n}.") for n in range(5)])

    assert len(index.search("providers logs", limit=2)) == 2


def test_an_empty_index_or_query_finds_nothing(index: ChunkIndex) -> None:
    assert index.search("providers", limit=3) == []
    index.add([chunk(0, "Providers keep logs.")])
    assert index.search(" ?! ", limit=3) == []


def test_removing_a_document_removes_all_its_chunks(index: ChunkIndex) -> None:
    index.add([chunk(0, "Providers keep logs.", "a"), chunk(1, "Logs are kept.", "a")])
    index.add([chunk(0, "Providers keep logs too.", "b")])

    index.remove_document("a")

    assert {result.chunk.document_id for result in index.search("logs", limit=5)} == {"b"}
    assert index.document_ids() == {"b"}


def test_document_ids_lists_what_is_indexed(index: ChunkIndex) -> None:
    assert index.document_ids() == set()

    index.add([chunk(0, "One.", "a"), chunk(0, "Two.", "b")])

    assert index.document_ids() == {"a", "b"}


def test_adding_the_same_chunks_again_does_not_duplicate_them(index: ChunkIndex) -> None:
    chunks = [chunk(0, "Providers keep logs."), chunk(1, "Authorities inspect logs.")]
    index.add(chunks)

    index.add(chunks)

    assert len(index.search("logs", limit=10)) == 2
