from pathlib import Path

from assistant.adapters.file_document_store import LocalFileDocumentStore
from assistant.domain.documents import Document

POLICY = Document(id="a1", title="policy", filename="policy.txt", chunk_count=2)


def test_writes_only_under_the_documents_directory(tmp_path: Path) -> None:
    LocalFileDocumentStore(tmp_path).save(POLICY, "Policy text.")

    written = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert written
    assert all(path.parts[0] == "documents" for path in written)


def test_a_new_instance_sees_earlier_documents(tmp_path: Path) -> None:
    LocalFileDocumentStore(tmp_path).save(POLICY, "Policy text.")

    reopened = LocalFileDocumentStore(tmp_path)

    assert reopened.load_all() == [(POLICY, "Policy text.")]


def test_listing_and_fetching_read_only_metadata(tmp_path: Path) -> None:
    store = LocalFileDocumentStore(tmp_path)
    store.save(POLICY, "Policy text.")
    (tmp_path / "documents" / f"{POLICY.id}.txt").unlink()

    assert store.list_documents() == [POLICY]
    assert store.get(POLICY.id) == POLICY
