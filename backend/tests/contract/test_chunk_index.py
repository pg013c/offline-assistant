"""Contract for the ChunkIndex port; every adapter must pass it."""

from collections.abc import Callable

import pytest

from assistant.adapters.keyword_index import KeywordChunkIndex
from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ChunkIndex

ADAPTERS: list[Callable[[], ChunkIndex]] = [KeywordChunkIndex]


def chunk(position: int, text: str) -> Chunk:
    return Chunk(id=f"doc:{position}", document_id="doc", position=position, text=text)


@pytest.fixture(params=ADAPTERS, ids=lambda adapter: adapter.__name__)
def index(request: pytest.FixtureRequest) -> ChunkIndex:
    factory: Callable[[], ChunkIndex] = request.param
    return factory()


def test_ranks_chunks_by_shared_words(index: ChunkIndex) -> None:
    index.add(
        [
            chunk(0, "Providers must keep technical documentation."),
            chunk(1, "Providers of high-risk systems must keep logs and technical documentation."),
            chunk(2, "Member states designate authorities."),
        ]
    )

    results = index.search("technical documentation for high-risk systems", limit=3)

    assert [result.chunk.id for result in results] == ["doc:1", "doc:0"]
    assert results[0].score > results[1].score


def test_ignores_case_and_stop_words(index: ChunkIndex) -> None:
    index.add([chunk(0, "The REGISTER of the providers"), chunk(1, "of the and a")])

    results = index.search("what is the register", limit=5)

    assert [result.chunk.id for result in results] == ["doc:0"]


def test_respects_the_limit(index: ChunkIndex) -> None:
    index.add([chunk(position, f"deployer duty {position}") for position in range(5)])

    assert len(index.search("deployer", limit=2)) == 2


def test_returns_nothing_when_no_word_is_shared(index: ChunkIndex) -> None:
    index.add([chunk(0, "Market surveillance authorities.")])

    assert index.search("biometric identification", limit=5) == []


def test_returns_nothing_when_empty(index: ChunkIndex) -> None:
    assert index.search("anything", limit=5) == []
