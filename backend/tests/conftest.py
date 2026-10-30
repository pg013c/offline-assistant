"""Shared pytest configuration.

Layout: tests/unit (fakes only, no I/O), tests/integration (real adapters, marker
`integration`), tests/contract (one suite per port), tests/architecture (layer rules).
The fixtures below build API apps from fake adapters, so route tests need no models, no
Qdrant and no disk, and wait for ingestion to finish.
"""

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.app import Adapters, create_app
from assistant.settings import Settings

# Ingestion may run on a worker thread; text documents settle within milliseconds.
SETTLE_TIMEOUT_SECONDS = 5.0


type ClientFor = Callable[[Path], TestClient]
type Settle = Callable[[TestClient, str], dict[str, Any]]


@pytest.fixture
def client_for() -> ClientFor:
    """Apps on fake adapters; apps built for the same directory share a store, as after a
    restart, and start with an empty index."""
    stores: dict[Path, FakeDocumentStore] = {}

    def build(data_dir: Path) -> TestClient:
        settings = Settings(
            data_dir=data_dir,
            models_dir=data_dir / "models",
            # The in-memory index returns only passages sharing a word with the question.
            min_similarity=0,
        )
        adapters = Adapters(
            store=stores.setdefault(data_dir, FakeDocumentStore()),
            index=InMemoryChunkIndex(),
            parser=TextDocumentParser(),
            queue=InlineIngestionQueue(),
            chat_model=FakeExtractiveChatModel(),
        )
        return TestClient(create_app(settings, adapters))

    return build


@pytest.fixture
def client(client_for: ClientFor, tmp_path: Path) -> Iterator[TestClient]:
    with client_for(tmp_path) as client:
        yield client


@pytest.fixture
def settle() -> Settle:
    """Waits until a document's ingestion has finished, or the wait times out."""
    return _settle


def _settle(client: TestClient, document_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + SETTLE_TIMEOUT_SECONDS
    while True:
        listed = {document["id"]: document for document in client.get("/api/documents").json()}
        document: dict[str, Any] = listed[document_id]
        if document["status"] != "processing" or time.monotonic() > deadline:
            return document
        time.sleep(0.01)
