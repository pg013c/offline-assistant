from importlib.metadata import version
from pathlib import Path

from fastapi.testclient import TestClient

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.app import Adapters, create_app
from assistant.settings import Settings


def test_health_reports_ok_and_package_version(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": version("assistant"), "network": False}


def test_health_is_documented_with_a_typed_response(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()

    operation = schema["paths"]["/api/health"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/HealthResponse"}
    assert schema["components"]["schemas"]["HealthResponse"]["required"] == [
        "status",
        "version",
        "network",
    ]


def test_health_reports_network_mode_when_it_is_on(tmp_path: Path) -> None:
    adapters = Adapters(
        store=FakeDocumentStore(),
        index=InMemoryChunkIndex(),
        parser=TextDocumentParser(),
        queue=InlineIngestionQueue(),
        chat_model=FakeExtractiveChatModel(),
    )
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path / "models", allow_network=True)

    with TestClient(create_app(settings, adapters)) as client:
        response = client.get("/api/health")

    assert response.json()["network"] is True
