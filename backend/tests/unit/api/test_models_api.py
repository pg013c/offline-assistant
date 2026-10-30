import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from assistant.adapters.fakes.chat_model import ScriptedChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.app import Adapters, create_app
from assistant.domain.answers import Answered, ModelAnswer, TextDelta, Usage
from assistant.settings import Settings

POLICY = b"Providers keep logs for six months."
USAGE = Usage(prompt_tokens=1, completion_tokens=1, first_token_ms=1.0, total_ms=2.0, attempts=1)


def local_client(tmp_path: Path) -> TestClient:
    """An app configured with a local model, so the test model is offered beside it."""
    adapters = Adapters(
        store=FakeDocumentStore(),
        index=InMemoryChunkIndex(),
        parser=TextDocumentParser(),
        queue=InlineIngestionQueue(),
        chat_model=ScriptedChatModel(
            [TextDelta("Six months [1]."), Answered(ModelAnswer("Six months [1].", (1,)), USAGE)],
            model_id="qwen3-8b",
        ),
    )
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path / "models", min_similarity=0)
    return TestClient(create_app(settings, adapters))


def chat(client: TestClient, body: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    response = client.post("/api/chat", json=body)
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    return response.status_code, events


def test_with_the_test_model_configured_only_it_is_offered(client: TestClient) -> None:
    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.json() == [{"id": "fake-extractive", "is_test_model": True, "is_default": True}]


def test_a_local_model_is_offered_as_the_default_beside_the_test_model(tmp_path: Path) -> None:
    with local_client(tmp_path) as client:
        models = client.get("/api/models").json()

    assert models == [
        {"id": "qwen3-8b", "is_test_model": False, "is_default": True},
        {"id": "fake-extractive", "is_test_model": True, "is_default": False},
    ]


def test_a_question_is_answered_by_the_model_it_names_or_by_the_default(tmp_path: Path) -> None:
    with local_client(tmp_path) as client:
        client.post("/api/documents", files={"file": ("policy.txt", POLICY, "text/plain")})
        _, named = chat(client, {"question": "How long are logs kept?", "model": "fake-extractive"})
        _, default = chat(client, {"question": "How long are logs kept?"})

    assert named[-1]["model_id"] == "fake-extractive"
    assert default[-1]["model_id"] == "qwen3-8b"


def test_an_unknown_model_is_a_422_in_the_standard_error_shape(client: TestClient) -> None:
    response = client.post("/api/chat", json={"question": "Anything?", "model": "gpt-latest"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_model"
    assert "fake-extractive" in response.json()["message"]
