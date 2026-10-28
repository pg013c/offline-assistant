from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from assistant.app import create_app
from assistant.settings import Settings

POLICY = b"Providers keep logs.\n\nAuthorities may inspect the logs."


def client_for(data_dir: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=data_dir)))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with client_for(tmp_path) as client:
        yield client


def upload(client: TestClient, filename: str, content: bytes) -> dict[str, object]:
    response = client.post("/api/documents", files={"file": (filename, content, "text/plain")})
    return {"status": response.status_code, "body": response.json()}


def test_upload_returns_the_new_document(client: TestClient) -> None:
    result = upload(client, "policy.txt", POLICY)

    assert result["status"] == 201
    body = result["body"]
    assert isinstance(body, dict)
    assert body["title"] == "policy"
    assert body["filename"] == "policy.txt"
    assert body["chunk_count"] == 2
    assert body["id"]


def test_uploaded_documents_are_listed(client: TestClient) -> None:
    created = upload(client, "policy.txt", POLICY)["body"]

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.json() == [created]


@pytest.mark.parametrize(
    ("filename", "content", "status", "code"),
    [
        ("policy.pdf", POLICY, 415, "unsupported_file_type"),
        ("policy.txt", b"x" * (5 * 1024 * 1024 + 1), 413, "file_too_large"),
        ("policy.txt", "Zażółć".encode("utf-16"), 422, "not_utf8_text"),
    ],
)
def test_rejected_uploads_return_the_standard_error_and_store_nothing(
    client: TestClient, filename: str, content: bytes, status: int, code: str
) -> None:
    result = upload(client, filename, content)

    assert result["status"] == status
    body = result["body"]
    assert isinstance(body, dict)
    assert body["code"] == code
    assert body["message"]
    assert body["details"] is None
    assert client.get("/api/documents").json() == []


def test_a_request_without_a_file_returns_the_standard_error_with_details(
    client: TestClient,
) -> None:
    response = client.post("/api/documents", data={"note": "no file here"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert body["message"]
    assert body["details"] == [{"field": "body.file", "message": "Field required"}]


def test_uploading_the_same_content_twice_returns_the_same_document(client: TestClient) -> None:
    first = upload(client, "policy.txt", POLICY)

    second = upload(client, "again.txt", POLICY)

    assert first["status"] == 201
    assert second["status"] == 201
    assert second["body"] == first["body"]
    assert client.get("/api/documents").json() == [first["body"]]


def test_documents_survive_a_restart(tmp_path: Path) -> None:
    with client_for(tmp_path) as before:
        created = upload(before, "policy.txt", POLICY)["body"]

    with client_for(tmp_path) as after:
        assert after.get("/api/documents").json() == [created]
