from assistant.domain.notes import Note


class InMemoryNoteStore:
    def save(self, note: Note) -> str:
        raise NotImplementedError

    def list_notes(self) -> list[Note]:
        raise NotImplementedError

    def get(self, note_id: str) -> Note | None:
        raise NotImplementedError
