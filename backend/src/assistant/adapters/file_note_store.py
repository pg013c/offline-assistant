"""Notes as files in the notes directory: `<id>.md` for the user, `<id>.json` to read back.

Files are created exclusively, so a note never replaces another, and only plain ids are
read, so no other path can be named (AI-11).
"""

import json
import re
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from assistant.domain.documents import ChunkLocation
from assistant.domain.notes import Note, NoteSource, render

_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[a-z0-9-]+$")


class FileNoteStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, note: Note) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        suffix = 1
        while True:
            note_id = note.id if suffix == 1 else f"{note.id}-{suffix}"
            try:
                # Exclusive creation: an existing note is never overwritten.
                with (self._directory / f"{note_id}.json").open("x", encoding="utf-8") as file:
                    json.dump(_record(replace(note, id=note_id)), file, ensure_ascii=False)
            except FileExistsError:
                suffix += 1
                continue
            saved = replace(note, id=note_id)
            (self._directory / f"{note_id}.md").write_text(render(saved), encoding="utf-8")
            return note_id

    def list_notes(self) -> list[Note]:
        if not self._directory.exists():
            return []
        notes = [
            _note(json.loads(path.read_text(encoding="utf-8")))
            for path in self._directory.glob("*.json")
        ]
        return sorted(notes, key=lambda note: note.created, reverse=True)

    def get(self, note_id: str) -> Note | None:
        if not _ID.fullmatch(note_id):
            return None
        path = self._directory / f"{note_id}.json"
        if not path.exists():
            return None
        return _note(json.loads(path.read_text(encoding="utf-8")))


def _record(note: Note) -> dict[str, Any]:
    record = asdict(note)
    record["created"] = note.created.isoformat()
    return record


def _note(record: dict[str, Any]) -> Note:
    return Note(
        id=record["id"],
        title=record["title"],
        content=record["content"],
        sources=tuple(
            NoteSource(
                number=source["number"],
                document_title=source["document_title"],
                location=ChunkLocation(
                    heading_path=tuple(source["location"]["heading_path"]),
                    article=source["location"]["article"],
                    paragraph=source["location"]["paragraph"],
                    page=source["location"]["page"],
                ),
                chunk_id=source["chunk_id"],
            )
            for source in record["sources"]
        ),
        created=datetime.fromisoformat(record["created"]),
    )
