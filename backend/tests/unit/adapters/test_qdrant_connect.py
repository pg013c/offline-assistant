import pytest
from qdrant_client import QdrantClient

from assistant.adapters.fakes.embedder import FakeEmbedder
from assistant.adapters.qdrant_chunk_index import QdrantChunkIndex


def test_a_programming_error_is_not_reported_as_an_unreachable_qdrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(self: QdrantClient) -> None:
        raise TypeError("a bug, not a network problem")

    monkeypatch.setattr(QdrantClient, "get_collections", broken)

    with pytest.raises(TypeError, match="a bug"):
        QdrantChunkIndex.connect("http://127.0.0.1:6333", FakeEmbedder(), prefix="unused")
