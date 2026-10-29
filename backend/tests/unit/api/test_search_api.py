from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.fakes.reranker import WordOverlapReranker
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.app import Adapters, create_app
from assistant.settings import Settings

# Fixtures from tests/conftest.py.
type Settle = Callable[[TestClient, str], dict[str, Any]]

POLICY = b"# Logs\n\nProviders keep logs for six months.\n\nAuthorities may inspect the logs."


def test_search_returns_ranked_passages_with_their_location(
    client: TestClient, settle: Settle
) -> None:
    created = client.post("/api/documents", files={"file": ("policy.md", POLICY, "text/plain")})
    settle(client, created.json()["id"])

    response = client.post("/api/search", json={"query": "Who may inspect the logs?", "limit": 1})

    assert response.status_code == 200
    [passage] = response.json()
    assert passage["text"] == "Authorities may inspect the logs."
    assert passage["document_id"] == created.json()["id"]
    assert passage["document_title"] == "policy"
    assert passage["chunk_id"].startswith(passage["document_id"] + ":")
    assert passage["location"] == {
        "heading_path": ["Logs"],
        "article": None,
        "paragraph": None,
        "page": None,
    }
    assert 0 <= passage["similarity"] <= 1


def test_search_without_documents_finds_nothing(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "Anything?"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": "x" * 2001},
        {"query": "logs", "limit": 0},
        {"query": "logs", "limit": 51},
    ],
)
def test_invalid_searches_get_the_standard_error(client: TestClient, body: dict[str, Any]) -> None:
    response = client.post("/api/search", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


LOGS = b"# Logs\n\nLogs of every system are kept by providers for months.\n\nProviders keep logs."


@pytest.fixture
def reranked(tmp_path: Path) -> Iterator[TestClient]:
    """An app on fakes with the word-overlap reranker configured."""
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path / "models", min_similarity=0)
    adapters = Adapters(
        store=FakeDocumentStore(),
        index=InMemoryChunkIndex(),
        parser=TextDocumentParser(),
        queue=InlineIngestionQueue(),
        chat_model=FakeExtractiveChatModel(),
        reranker=WordOverlapReranker(),
    )
    with TestClient(create_app(settings, adapters)) as client:
        yield client


def search(client: TestClient, settle: Settle, body: dict[str, Any]) -> list[dict[str, Any]]:
    created = client.post("/api/documents", files={"file": ("logs.md", LOGS, "text/plain")})
    settle(client, created.json()["id"])
    response = client.post("/api/search", json=body)
    assert response.status_code == 200
    hits: list[dict[str, Any]] = response.json()
    return hits


def test_with_a_reranker_hits_are_reranked_and_carry_its_score(
    reranked: TestClient, settle: Settle
) -> None:
    hits = search(reranked, settle, {"query": "Do providers keep logs?"})

    assert all(hit["rerank_score"] is not None for hit in hits)
    scores = [hit["rerank_score"] for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_a_search_can_ask_for_the_hybrid_order(reranked: TestClient, settle: Settle) -> None:
    reranked_hits = search(reranked, settle, {"query": "Do providers keep logs?"})
    hybrid = reranked.post(
        "/api/search", json={"query": "Do providers keep logs?", "rerank": False}
    ).json()

    assert all(hit["rerank_score"] is None for hit in hybrid)
    assert {hit["chunk_id"] for hit in hybrid} == {hit["chunk_id"] for hit in reranked_hits}


def test_without_a_reranker_hits_have_no_rerank_score(client: TestClient, settle: Settle) -> None:
    hits = search(client, settle, {"query": "Do providers keep logs?"})

    assert hits
    assert all(hit["rerank_score"] is None for hit in hits)


def test_asking_for_reranking_without_a_reranker_is_a_conflict(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "logs", "rerank": True})

    assert response.status_code == 409
    assert response.json()["code"] == "reranker_off"
