from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from assistant.adapters.file_note_store import FileNoteStore
from assistant.domain.documents import ChunkLocation
from assistant.domain.notes import Note, NoteSource

# Fixtures from tests/conftest.py: the app keeps notes in <data dir>/notes.

OLDER = Note(
    id="20261030-091507-breach-duties",
    title="Breach duties",
    content="- Notify within 72 hours [1]",
    sources=(
        NoteSource(
            number=1,
            document_title="GDPR (EN)",
            location=ChunkLocation(
                heading_path=("Article 33",), article="33", paragraph="1", page=52
            ),
            chunk_id="gdpr:612",
        ),
    ),
    created=datetime(2026, 10, 30, 9, 15, 7, tzinfo=UTC),
)
NEWER = Note(
    id="20261030-101000-deployer-duties",
    title="Deployer duties",
    content="Use the system as instructed [1].",
    sources=(),
    created=datetime(2026, 10, 30, 10, 10, 0, tzinfo=UTC),
)


def test_without_notes_the_list_is_empty(client: TestClient) -> None:
    response = client.get("/api/notes")

    assert response.status_code == 200
    assert response.json() == []


def test_notes_are_listed_newest_first(client: TestClient, tmp_path: Path) -> None:
    store = FileNoteStore(tmp_path / "notes")
    store.save(OLDER)
    store.save(NEWER)

    response = client.get("/api/notes")

    assert response.json() == [
        {"id": NEWER.id, "title": "Deployer duties", "created": "2026-10-30T10:10:00Z"},
        {"id": OLDER.id, "title": "Breach duties", "created": "2026-10-30T09:15:07Z"},
    ]


def test_a_note_is_returned_with_its_content_sources_and_markdown(
    client: TestClient, tmp_path: Path
) -> None:
    FileNoteStore(tmp_path / "notes").save(OLDER)

    response = client.get(f"/api/notes/{OLDER.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Breach duties"
    assert body["content"] == "- Notify within 72 hours [1]"
    assert body["sources"] == [
        {
            "number": 1,
            "document_title": "GDPR (EN)",
            "chunk_id": "gdpr:612",
            "location": {
                "heading_path": ["Article 33"],
                "article": "33",
                "paragraph": "1",
                "page": 52,
            },
        }
    ]
    assert body["markdown"].startswith("# Breach duties\n")


def test_an_unknown_note_is_a_404_in_the_standard_error_shape(client: TestClient) -> None:
    response = client.get("/api/notes/20261030-000000-nothing")

    assert response.status_code == 404
    assert response.json()["code"] == "note_not_found"


def test_an_id_that_names_a_path_is_not_found(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")

    response = client.get("/api/notes/..%2Fsecret")

    assert response.status_code == 404
