"""Shared pytest configuration.

Layout: tests/unit (fakes only, no I/O), tests/integration (real adapters, marker
`integration`), tests/contract (one suite per port), tests/architecture (layer rules).
The fixtures below build API apps that read text only and wait for background ingestion.
"""

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.app import create_app
from assistant.settings import Settings

# Ingestion runs on a worker thread; text documents settle within milliseconds.
SETTLE_TIMEOUT_SECONDS = 5.0


type ClientFor = Callable[[Path], TestClient]
type Settle = Callable[[TestClient, str], dict[str, Any]]


@pytest.fixture
def client_for() -> ClientFor:
    """Apps that read text only, so API tests need no parsing models."""

    def build(data_dir: Path) -> TestClient:
        return TestClient(create_app(Settings(data_dir=data_dir, document_parser="text-only")))

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
