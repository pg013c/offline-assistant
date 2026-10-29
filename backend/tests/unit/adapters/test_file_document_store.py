from dataclasses import replace
from pathlib import Path

from assistant.adapters.file_document_store import LocalFileDocumentStore
from assistant.domain.documents import Chunk, ChunkLocation, Document

POLICY = Document(
    id="a1", title="policy", filename="policy.pdf", chunk_count=0, status="processing"
)
CHUNKS = [
    Chunk(
        id="a1:0",
        document_id="a1",
        position=0,
        text="Text.",
        location=ChunkLocation(heading_path=("Article 1",), article="1", page=1),
    )
]


def test_writes_only_under_the_documents_directory(tmp_path: Path) -> None:
    store = LocalFileDocumentStore(tmp_path)
    store.save_upload(POLICY, b"%PDF policy")
    store.save_chunks(POLICY.id, CHUNKS)

    written = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert written
    assert all(path.parts[0] == "documents" for path in written)


def test_the_original_keeps_the_upload_extension(tmp_path: Path) -> None:
    LocalFileDocumentStore(tmp_path).save_upload(POLICY, b"%PDF policy")

    assert (tmp_path / "documents" / "a1.pdf").read_bytes() == b"%PDF policy"


def test_a_new_instance_sees_earlier_documents_and_chunks(tmp_path: Path) -> None:
    store = LocalFileDocumentStore(tmp_path)
    store.save_upload(POLICY, b"%PDF policy")
    store.update(replace(POLICY, status="ready", chunk_count=1, page_count=1))
    store.save_chunks(POLICY.id, CHUNKS)

    reopened = LocalFileDocumentStore(tmp_path)

    assert reopened.get(POLICY.id) == replace(POLICY, status="ready", chunk_count=1, page_count=1)
    assert reopened.load_chunks(POLICY.id) == CHUNKS


def test_listing_and_fetching_read_only_metadata(tmp_path: Path) -> None:
    store = LocalFileDocumentStore(tmp_path)
    store.save_upload(POLICY, b"%PDF policy")
    (tmp_path / "documents" / "a1.pdf").unlink()

    assert store.list_documents() == [POLICY]
    assert store.get(POLICY.id) == POLICY


def test_metadata_without_a_status_loads_as_processing(tmp_path: Path) -> None:
    # F-01 stored no status; such documents need parsing again.
    directory = tmp_path / "documents"
    directory.mkdir()
    (directory / "f01.txt").write_text("Old text.", encoding="utf-8")
    (directory / "f01.json").write_text(
        '{"id": "f01", "title": "old", "filename": "old.txt", "chunk_count": 1}', encoding="utf-8"
    )

    document = LocalFileDocumentStore(tmp_path).get("f01")

    assert document is not None
    assert document.status == "processing"


def test_deleting_leaves_no_file_of_the_document(tmp_path: Path) -> None:
    store = LocalFileDocumentStore(tmp_path)
    store.save_upload(POLICY, b"%PDF policy")
    store.save_chunks(POLICY.id, CHUNKS)

    store.delete(POLICY.id)

    assert list((tmp_path / "documents").iterdir()) == []
