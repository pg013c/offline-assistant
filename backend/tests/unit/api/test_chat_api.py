import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.documents import chunk_document, document_id_for

# Fixtures from tests/conftest.py.
type ClientFor = Callable[[Path], TestClient]
type Settle = Callable[[TestClient, str], dict[str, Any]]
type Upload = Callable[..., None]


POLICY = (
    b"Providers keep logs for six months. Logs record every access.\n\nAuthorities inspect logs."
)
QUESTION = {"question": "How long do providers keep logs?"}


@pytest.fixture
def upload(settle: Settle) -> Upload:
    def upload_and_wait(
        client: TestClient, filename: str = "policy.txt", content: bytes = POLICY
    ) -> None:
        response = client.post("/api/documents", files={"file": (filename, content, "text/plain")})
        assert response.status_code == 202
        assert settle(client, response.json()["id"])["status"] == "ready"

    return upload_and_wait


def ask(client: TestClient) -> tuple[str, list[dict[str, Any]]]:
    response = client.post("/api/chat", json=QUESTION)
    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    return response.headers["content-type"], events


def test_answer_is_a_stream_of_text_then_citation_then_end(
    client: TestClient, upload: Upload
) -> None:
    upload(client)

    content_type, events = ask(client)

    assert content_type.startswith("text/event-stream")
    kinds = [event["type"] for event in events]
    first_citation = kinds.index("citation")
    assert first_citation > 1
    assert set(kinds[:first_citation]) == {"text"}
    assert set(kinds[first_citation:-1]) == {"citation"}
    assert events[-1] == {
        "type": "end",
        "model_id": "fake-extractive",
        "found": True,
        "is_test_model": True,
    }


def test_citation_events_carry_the_quoted_passage(client: TestClient, upload: Upload) -> None:
    upload(client)

    _, events = ask(client)

    citation = next(event for event in events if event["type"] == "citation")
    assert citation["document_title"] == "policy"
    parsed = TextDocumentParser().parse("policy.txt", POLICY)
    chunks = {chunk.id: chunk.text for chunk in chunk_document(document_id_for(POLICY), parsed)}
    assert citation["quote"] in chunks[citation["chunk_id"]]
    assert citation["chunk_id"].startswith(citation["document_id"] + ":")


def test_citation_events_carry_the_location_of_the_chunk(
    client: TestClient, upload: Upload
) -> None:
    upload(client, "policy.md", b"# Logs\n\n" + POLICY)

    _, events = ask(client)

    citation = next(event for event in events if event["type"] == "citation")
    assert citation["location"] == {
        "heading_path": ["Logs"],
        "article": None,
        "paragraph": None,
        "page": None,
    }


def test_without_documents_the_stream_has_no_citation(client: TestClient) -> None:
    _, events = ask(client)

    assert [event["type"] for event in events] == ["text", "end"]
    assert events[-1]["found"] is False


def test_documents_are_searchable_after_a_restart(
    tmp_path: Path, client_for: ClientFor, upload: Upload
) -> None:
    with client_for(tmp_path) as before:
        upload(before)

    with client_for(tmp_path) as after:
        _, events = ask(after)

    assert any(event["type"] == "citation" for event in events)


def test_openapi_documents_the_event_stream_and_its_event_types(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()

    content = schema["paths"]["/api/chat"]["post"]["responses"]["200"]["content"]
    assert "text/event-stream" in content
    assert {"ChatEvent", "ChatTextEvent", "ChatCitationEvent", "ChatEndEvent"} <= set(
        schema["components"]["schemas"]
    )


def test_an_empty_question_returns_the_standard_error(client: TestClient) -> None:
    response = client.post("/api/chat", json={"question": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert [detail["field"] for detail in body["details"]] == ["body.question"]
