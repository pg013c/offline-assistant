from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from assistant.domain.errors import DocumentRejected, FileTooLarge, UnsupportedFileType
from assistant.services.documents import MAX_UPLOAD_BYTES, NO_TEXT

# Fixtures from tests/conftest.py.
type ClientFor = Callable[[Path], TestClient]
type Settle = Callable[[TestClient, str], dict[str, Any]]


POLICY = b"Providers keep logs.\n\nAuthorities may inspect the logs."


def upload(client: TestClient, filename: str, content: bytes) -> dict[str, object]:
    response = client.post("/api/documents", files={"file": (filename, content, "text/plain")})
    return {"status": response.status_code, "body": response.json()}


def test_upload_is_accepted_and_the_document_becomes_ready(
    client: TestClient, settle: Settle
) -> None:
    result = upload(client, "policy.txt", POLICY)

    assert result["status"] == 202
    body = result["body"]
    assert isinstance(body, dict)
    assert (body["title"], body["filename"]) == ("policy", "policy.txt")
    assert body["status"] in {"processing", "ready"}
    ready = settle(client, str(body["id"]))
    assert ready == {
        "id": body["id"],
        "title": "policy",
        "filename": "policy.txt",
        "status": "ready",
        "chunk_count": 2,
        "page_count": None,
        "failure_reason": None,
    }


def test_uploaded_documents_are_listed(client: TestClient, settle: Settle) -> None:
    created = upload(client, "policy.txt", POLICY)["body"]
    assert isinstance(created, dict)
    ready = settle(client, str(created["id"]))

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.json() == [ready]


def test_a_document_without_text_fails_with_its_reason(client: TestClient, settle: Settle) -> None:
    created = upload(client, "empty.md", b"\n\n   \n")["body"]
    assert isinstance(created, dict)

    failed = settle(client, str(created["id"]))

    assert (failed["status"], failed["failure_reason"]) == ("failed", NO_TEXT)


@pytest.mark.parametrize(
    ("filename", "content", "status", "code"),
    [
        ("slides.pptx", POLICY, 415, "unsupported_file_type"),
        ("policy.txt", b"x" * (MAX_UPLOAD_BYTES + 1), 413, "file_too_large"),
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


def test_uploading_the_same_content_twice_returns_the_same_document(
    client: TestClient, settle: Settle
) -> None:
    first = upload(client, "policy.txt", POLICY)["body"]
    assert isinstance(first, dict)
    ready = settle(client, str(first["id"]))

    second = upload(client, "again.txt", POLICY)

    assert second["status"] == 202
    assert second["body"] == ready
    assert client.get("/api/documents").json() == [ready]


def test_documents_survive_a_restart(tmp_path: Path, settle: Settle, client_for: ClientFor) -> None:
    with client_for(tmp_path) as before:
        created = upload(before, "policy.txt", POLICY)["body"]
        assert isinstance(created, dict)
        ready = settle(before, str(created["id"]))

    with client_for(tmp_path) as after:
        assert after.get("/api/documents").json() == [ready]


class EmptyFile(UnsupportedFileType):
    """A rejection added later, without its own HTTP mapping."""


class RejectingDocuments:
    def upload(self, filename: str, content: bytes) -> object:
        raise EmptyFile(f"{filename}: empty")


def test_a_new_kind_of_rejection_falls_back_to_its_parent_mapping(client: TestClient) -> None:
    client.app.state.document_service = RejectingDocuments()  # type: ignore[attr-defined]

    result = upload(client, "empty.txt", b"")

    assert result["status"] == 415
    body = result["body"]
    assert isinstance(body, dict)
    assert body["code"] == "unsupported_file_type"


class UnmappedRejection(DocumentRejected):
    """A rejection with no mapping anywhere in its class hierarchy."""


class RejectingWithUnmapped:
    def upload(self, filename: str, content: bytes) -> object:
        raise UnmappedRejection(f"{filename}: rejected")


def test_an_unmapped_rejection_is_still_reported_with_the_standard_body(client: TestClient) -> None:
    client.app.state.document_service = RejectingWithUnmapped()  # type: ignore[attr-defined]

    result = upload(client, "file.txt", b"x")

    assert result["status"] == 422
    body = result["body"]
    assert isinstance(body, dict)
    assert body["code"] == "document_rejected"


class RecordingDocuments:
    def __init__(self) -> None:
        self.received: list[int] = []

    def upload(self, filename: str, content: bytes) -> object:
        self.received.append(len(content))
        raise FileTooLarge(f"{filename}: too large")


def test_an_oversized_upload_is_not_read_beyond_the_limit(client: TestClient) -> None:
    documents = RecordingDocuments()
    client.app.state.document_service = documents  # type: ignore[attr-defined]

    upload(client, "big.txt", b"x" * (MAX_UPLOAD_BYTES * 2))

    assert documents.received == [MAX_UPLOAD_BYTES + 1]


def test_a_deleted_document_leaves_the_list_and_the_answers(
    client: TestClient, settle: Settle
) -> None:
    created = upload(client, "policy.txt", POLICY)["body"]
    assert isinstance(created, dict)
    settle(client, str(created["id"]))

    response = client.delete(f"/api/documents/{created['id']}")

    assert response.status_code == 204
    assert client.get("/api/documents").json() == []
    answer = client.post("/api/chat", json={"question": "Who may inspect the logs?"}).text
    assert '"type":"citation"' not in answer.replace(" ", "")


def test_reindexing_returns_the_document_as_processing_and_it_becomes_ready(
    client: TestClient, settle: Settle
) -> None:
    created = upload(client, "policy.txt", POLICY)["body"]
    assert isinstance(created, dict)
    before = settle(client, str(created["id"]))

    response = client.post(f"/api/documents/{created['id']}/reindex")

    assert response.status_code == 202
    assert response.json()["id"] == created["id"]
    assert response.json()["status"] in {"processing", "ready"}
    assert settle(client, str(created["id"])) == before


@pytest.mark.parametrize(
    ("method", "path"),
    [("DELETE", "/api/documents/unknown"), ("POST", "/api/documents/unknown/reindex")],
)
def test_an_unknown_document_is_reported_as_not_found(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path)

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "document_not_found"
    assert body["message"]
    assert body["details"] is None


def test_a_document_lists_its_chunks_with_their_locations(
    client: TestClient, settle: Settle
) -> None:
    created = upload(client, "policy.md", b"# Logs\n\n" + POLICY)["body"]
    assert isinstance(created, dict)
    settle(client, str(created["id"]))

    response = client.get(f"/api/documents/{created['id']}/chunks")

    assert response.status_code == 200
    assert response.json() == [
        {
            "chunk_id": f"{created['id']}:{position}",
            "position": position,
            "location": {
                "heading_path": ["Logs"],
                "article": None,
                "paragraph": None,
                "page": None,
            },
        }
        for position in (0, 1)
    ]


def test_the_chunks_of_an_unknown_document_are_not_found(client: TestClient) -> None:
    response = client.get("/api/documents/unknown/chunks")

    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"
