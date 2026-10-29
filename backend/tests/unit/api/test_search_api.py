from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

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
