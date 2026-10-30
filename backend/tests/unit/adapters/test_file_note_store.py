from datetime import UTC, datetime
from pathlib import Path

from structlog.testing import capture_logs

from assistant.adapters.file_note_store import FileNoteStore
from assistant.domain.notes import Note, render

NOTE = Note(
    id="20261030-091507-breach",
    title="Breach",
    content="Notify within 72 hours [1].",
    sources=(),
    created=datetime(2026, 10, 30, 9, 15, 7, tzinfo=UTC),
)


def test_a_note_is_a_markdown_file_in_the_notes_directory(tmp_path: Path) -> None:
    store = FileNoteStore(tmp_path / "notes")

    store.save(NOTE)

    assert (tmp_path / "notes" / f"{NOTE.id}.md").read_text(encoding="utf-8") == render(NOTE)
    assert {path.parent for path in (tmp_path / "notes").iterdir()} == {tmp_path / "notes"}


def test_an_id_that_names_a_path_is_never_read(tmp_path: Path) -> None:
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    store = FileNoteStore(tmp_path / "notes")
    store.save(NOTE)

    assert store.get("../secret") is None
    assert store.get("/etc/passwd") is None
    assert store.get(".") is None


def test_an_empty_directory_lists_no_notes(tmp_path: Path) -> None:
    assert FileNoteStore(tmp_path / "missing").list_notes() == []


def test_a_damaged_or_foreign_file_is_skipped_and_logged_by_id_only(tmp_path: Path) -> None:
    directory = tmp_path / "notes"
    store = FileNoteStore(directory)
    store.save(NOTE)
    (directory / "20261030-100000-broken.json").write_text("{not json", encoding="utf-8")
    (directory / "my-own.json").write_text("{}", encoding="utf-8")

    with capture_logs() as logs:
        notes = store.list_notes()

    assert [note.id for note in notes] == [NOTE.id]
    assert store.get("20261030-100000-broken") is None
    warnings = [entry for entry in logs if entry["event"] == "note_unreadable"]
    assert [entry["note_id"] for entry in warnings] == ["20261030-100000-broken"] * len(warnings)
    assert warnings


def test_saving_leaves_only_the_note_files(tmp_path: Path) -> None:
    directory = tmp_path / "notes"

    FileNoteStore(directory).save(NOTE)

    assert sorted(path.name for path in directory.iterdir()) == [
        f"{NOTE.id}.json",
        f"{NOTE.id}.md",
    ]
