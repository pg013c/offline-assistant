import threading
import time
from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.app import Adapters, create_app
from assistant.domain.documents import Chunk, Document
from assistant.settings import Settings

RELEASE_AFTER_SECONDS = 2.0


class SlowToFillIndex(InMemoryChunkIndex):
    """Adding chunks blocks, as embedding a whole corpus does, until released."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def add(self, chunks: Sequence[Chunk]) -> None:
        self.release.wait(RELEASE_AFTER_SECONDS)
        super().add(chunks)


def test_the_api_answers_while_the_index_is_being_rebuilt(tmp_path: Path) -> None:
    store = FakeDocumentStore()
    document = Document(
        id="a1", title="policy", filename="policy.txt", chunk_count=1, status="ready"
    )
    store.save_upload(document, b"Providers keep logs.")
    store.save_chunks(
        "a1", [Chunk(id="a1:0", document_id="a1", position=0, text="Providers keep logs.")]
    )
    index = SlowToFillIndex()
    app = create_app(
        Settings(data_dir=tmp_path, models_dir=tmp_path, min_similarity=0),
        Adapters(
            store=store,
            index=index,
            parser=TextDocumentParser(),
            queue=InlineIngestionQueue(),
            chat_model=FakeExtractiveChatModel(),
        ),
    )
    started = time.monotonic()

    with TestClient(app) as client:
        response = client.get("/api/health")
        answered_after = time.monotonic() - started
        index.release.set()

    assert response.status_code == 200
    assert answered_after < RELEASE_AFTER_SECONDS / 2


class SlowReranker:
    """Scoring blocks until released, as loading the real model does; counts its calls."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls = 0

    @property
    def model_id(self) -> str:
        return "slow"

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        self.release.wait(RELEASE_AFTER_SECONDS)
        self.calls += 1
        return [0.0 for _ in passages]


def test_the_reranker_is_loaded_at_startup_without_delaying_the_api(tmp_path: Path) -> None:
    reranker = SlowReranker()
    app = create_app(
        Settings(data_dir=tmp_path, models_dir=tmp_path, min_similarity=0),
        Adapters(
            store=FakeDocumentStore(),
            index=InMemoryChunkIndex(),
            parser=TextDocumentParser(),
            queue=InlineIngestionQueue(),
            chat_model=FakeExtractiveChatModel(),
            reranker=reranker,
        ),
    )
    started = time.monotonic()

    with TestClient(app) as client:
        response = client.get("/api/health")
        answered_after = time.monotonic() - started
        reranker.release.set()

    assert response.status_code == 200
    assert answered_after < RELEASE_AFTER_SECONDS / 2
    # Shutting down waits for the warm-up, which scored one pair before any question.
    assert reranker.calls == 1
