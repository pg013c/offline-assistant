from typing import Protocol

from assistant.domain.notes import Note


class NoteStore(Protocol):
    """Where the agent's notes are kept, on this machine only (AI-11)."""

    def save(self, note: Note) -> str:
        """Store the note and return its id; a taken id gets a suffix, nothing is overwritten."""
        ...

    def list_notes(self) -> list[Note]:
        """Every note, newest first."""
        ...

    def get(self, note_id: str) -> Note | None:
        """The note with this id, or None."""
        ...
