"""Contract for the NoteStore port; every adapter must pass it."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from assistant.adapters.fakes.note_store import InMemoryNoteStore
from assistant.adapters.file_note_store import FileNoteStore
from assistant.domain.documents import ChunkLocation
from assistant.domain.notes import Note, NoteSource
from assistant.ports.note_store import NoteStore

ADAPTERS: list[Callable[[Path], NoteStore]] = [
    lambda _: InMemoryNoteStore(),
    lambda directory: FileNoteStore(directory / "notes"),
]

FIRST = Note(
    id="20261030-091507-deployer-duties",
    title="Deployer duties",
    content="- Use the system as instructed [1]",
    sources=(
        NoteSource(
            number=1,
            document_title="AI Act (EN)",
            location=ChunkLocation(heading_path=("Article 26",), article="26", paragraph="1"),
            chunk_id="ai:410",
        ),
    ),
    created=datetime(2026, 10, 30, 9, 15, 7, tzinfo=UTC),
)
SECOND = replace(
    FIRST,
    id="20261030-101000-breach",
    title="Breach",
    content="Notify within 72 hours [1].",
    created=datetime(2026, 10, 30, 10, 10, 0, tzinfo=UTC),
)


@pytest.fixture(params=ADAPTERS, ids=["in-memory", "file"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> NoteStore:
    factory: Callable[[Path], NoteStore] = request.param
    return factory(tmp_path)


def test_a_saved_note_is_read_back_by_its_id(store: NoteStore) -> None:
    saved = store.save(FIRST)

    assert saved == FIRST.id
    assert store.get(FIRST.id) == FIRST


def test_notes_are_listed_newest_first(store: NoteStore) -> None:
    store.save(FIRST)
    store.save(SECOND)

    assert [note.id for note in store.list_notes()] == [SECOND.id, FIRST.id]


def test_an_unknown_id_is_none(store: NoteStore) -> None:
    assert store.get("20261030-000000-nothing") is None


def test_a_note_with_a_taken_id_gets_a_suffix_and_the_first_is_kept(store: NoteStore) -> None:
    store.save(FIRST)

    saved = store.save(replace(FIRST, content="Something else [1]."))

    assert saved == f"{FIRST.id}-2"
    assert store.get(FIRST.id) == FIRST
    note = store.get(saved)
    assert note is not None
    assert note.content == "Something else [1]."
