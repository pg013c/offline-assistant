"""The Qdrant chunk index (ADR 0017). Needs `make qdrant`."""

import os
import uuid
from collections.abc import Iterator

import pytest
from qdrant_client import QdrantClient

from assistant.adapters.fakes.embedder import FakeEmbedder
from assistant.adapters.qdrant_chunk_index import IndexNotReady, QdrantChunkIndex, point_id
from assistant.domain.documents import Chunk, ChunkLocation

pytestmark = pytest.mark.integration

QDRANT_URL = os.environ.get("ASSISTANT_QDRANT_URL", "http://127.0.0.1:6333")
CHUNK = Chunk(
    id="doc:2",
    document_id="doc",
    position=2,
    text="1. Irrespective of whether an AI system is placed on the market...",
    location=ChunkLocation(
        heading_path=("CHAPTER III", "Article 6"), article="6", paragraph="1", page=53
    ),
)


class OtherEmbedder(FakeEmbedder):
    @property
    def model_id(self) -> str:
        return "other-embedder"


@pytest.fixture
def prefix() -> Iterator[str]:
    name = f"test-{uuid.uuid4().hex[:8]}"
    yield name
    client = QdrantClient(url=QDRANT_URL)
    for collection in client.get_collections().collections:
        if collection.name.startswith(name):
            client.delete_collection(collection.name)


def test_each_chunk_is_stored_with_both_vectors_and_its_payload(prefix: str) -> None:
    index = QdrantChunkIndex.connect(QDRANT_URL, FakeEmbedder(), prefix=prefix)

    index.add([CHUNK])

    [point] = QdrantClient(url=QDRANT_URL).retrieve(
        index.collection, ids=[point_id(CHUNK.id)], with_payload=True, with_vectors=True
    )
    assert point.payload == {
        "chunk_id": "doc:2",
        "document_id": "doc",
        "position": 2,
        "text": CHUNK.text,
        "location": {
            "heading_path": ["CHAPTER III", "Article 6"],
            "article": "6",
            "paragraph": "1",
            "page": 53,
        },
    }
    assert isinstance(point.vector, dict)
    dense = point.vector["dense"]
    assert isinstance(dense, list)
    assert len(dense) == FakeEmbedder().dimensions
    assert point.vector["bm25"]


def test_search_returns_the_chunk_as_it_was_added(prefix: str) -> None:
    index = QdrantChunkIndex.connect(QDRANT_URL, FakeEmbedder(), prefix=prefix)
    index.add([CHUNK])

    [result] = index.search("When is an AI system placed on the market?", limit=1)

    assert result.chunk == CHUNK


def test_another_embedding_model_gets_its_own_collection(prefix: str) -> None:
    first = QdrantChunkIndex.connect(QDRANT_URL, FakeEmbedder(), prefix=prefix)
    second = QdrantChunkIndex.connect(QDRANT_URL, OtherEmbedder(), prefix=prefix)
    first.add([CHUNK])

    assert first.collection != second.collection
    assert first.document_ids() == {"doc"}
    assert second.document_ids() == set()


def test_an_unreachable_qdrant_names_the_url_and_the_command() -> None:
    with pytest.raises(IndexNotReady, match=r"http://127\.0\.0\.1:9.*make qdrant"):
        QdrantChunkIndex.connect("http://127.0.0.1:9", FakeEmbedder(), prefix="unused")


def test_collections_carry_the_indexed_text_schema_version(prefix: str) -> None:
    index = QdrantChunkIndex.connect(QDRANT_URL, FakeEmbedder(), prefix=prefix)

    assert index.collection.endswith("-v2")
