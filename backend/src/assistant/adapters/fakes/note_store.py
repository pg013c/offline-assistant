"""Notes kept in memory, for tests."""

from dataclasses import replace

from assistant.domain.notes import Note


class InMemoryNoteStore:
    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}

    def save(self, note: Note) -> str:
        saved = _free_id(note.id, self._notes)
        self._notes[saved] = replace(note, id=saved)
        return saved

    def list_notes(self) -> list[Note]:
        return sorted(self._notes.values(), key=lambda note: note.created, reverse=True)

    def get(self, note_id: str) -> Note | None:
        return self._notes.get(note_id)


def _free_id(wanted: str, taken: dict[str, Note]) -> str:
    candidate, suffix = wanted, 1
    while candidate in taken:
        suffix += 1
        candidate = f"{wanted}-{suffix}"
    return candidate
