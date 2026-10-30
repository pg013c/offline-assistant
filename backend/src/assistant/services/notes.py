"""The notes the agent saved, for the user to read back (F-07a)."""

from assistant.domain.errors import NoteNotFound
from assistant.domain.notes import Note
from assistant.ports.note_store import NoteStore


class NoteService:
    def __init__(self, store: NoteStore) -> None:
        self._store = store

    def list_notes(self) -> list[Note]:
        """Every note, newest first."""
        return self._store.list_notes()

    def get(self, note_id: str) -> Note:
        """The note with this id; `NoteNotFound` if there is none."""
        note = self._store.get(note_id)
        if note is None:
            raise NoteNotFound(note_id)
        return note
