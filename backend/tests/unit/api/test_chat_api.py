import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.app import create_app
from assistant.settings import Settings

POLICY = (
    b"Providers keep logs for six months. Logs record every access.\n\nAuthorities inspect logs."
)
QUESTION = {"question": "How long do providers keep logs?"}


def client_for(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir)))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with client_for(tmp_path) as client:
        yield client


def upload(client: TestClient) -> None:
    response = client.post("/api/documents", files={"file": ("policy.txt", POLICY, "text/plain")})
    assert response.status_code == 201


def ask(client: TestClient) -> tuple[str, list[dict[str, Any]]]:
    response = client.post("/api/chat", json=QUESTION)
    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    return response.headers["content-type"], events


def test_answer_is_a_stream_of_text_then_citation_then_end(client: TestClient) -> None:
    upload(client)

    content_type, events = ask(client)

    assert content_type.startswith("text/event-stream")
    kinds = [event["type"] for event in events]
    first_citation = kinds.index("citation")
    assert first_citation > 1
    assert set(kinds[:first_citation]) == {"text"}
    assert set(kinds[first_citation:-1]) == {"citation"}
    assert events[-1] == {"type": "end", "model_id": "fake-extractive", "found": True}


def test_citation_events_carry_the_quoted_passage(client: TestClient) -> None:
    upload(client)

    _, events = ask(client)

    citation = next(event for event in events if event["type"] == "citation")
    assert citation["document_title"] == "policy"
    assert citation["quote"] in POLICY.decode()
    assert citation["chunk_id"].startswith(citation["document_id"] + ":")


def test_without_documents_the_stream_has_no_citation(client: TestClient) -> None:
    _, events = ask(client)

    assert [event["type"] for event in events] == ["text", "end"]
    assert events[-1]["found"] is False


def test_documents_are_searchable_after_a_restart(tmp_path: Path) -> None:
    with client_for(tmp_path) as before:
        upload(before)

    with client_for(tmp_path) as after:
        _, events = ask(after)

    assert any(event["type"] == "citation" for event in events)


def test_openapi_documents_the_event_stream_and_its_event_types(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()

    content = schema["paths"]["/api/chat"]["post"]["responses"]["200"]["content"]
    assert "text/event-stream" in content
    assert {"ChatTextEvent", "ChatCitationEvent", "ChatEndEvent"} <= set(
        schema["components"]["schemas"]
    )
