"""Notes as files in the notes directory: `<id>.md` for the user, `<id>.json` to read back.

Each file is written to a temporary name and linked into place, which fails if the name is
taken: a note never replaces another, and a half-written file is never read. Only files
named by a plain id are read, so no other path can be named (AI-11); one that cannot be
read is skipped and logged by its id.
"""

import json
import os
import re
import tempfile
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from assistant.domain.documents import ChunkLocation
from assistant.domain.notes import Note, NoteSource, render

log = structlog.get_logger(__name__)

_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[a-z0-9-]+$")


class FileNoteStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, note: Note) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        suffix = 1
        while True:
            saved = replace(note, id=note.id if suffix == 1 else f"{note.id}-{suffix}")
            # The Markdown first, then the record that makes the note listed.
            if self._place(f"{saved.id}.md", render(saved)):
                if self._place(f"{saved.id}.json", json.dumps(_record(saved), ensure_ascii=False)):
                    return saved.id
                (self._directory / f"{saved.id}.md").unlink()
            suffix += 1

    def list_notes(self) -> list[Note]:
        if not self._directory.exists():
            return []
        notes = [self.get(path.stem) for path in self._directory.glob("*.json")]
        return sorted(
            (note for note in notes if note is not None),
            key=lambda note: note.created,
            reverse=True,
        )

    def get(self, note_id: str) -> Note | None:
        if not _ID.fullmatch(note_id):
            return None
        path = self._directory / f"{note_id}.json"
        if not path.exists():
            return None
        try:
            return _note(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, KeyError, TypeError):
            log.warning("note_unreadable", note_id=note_id)
            return None

    def _place(self, name: str, text: str) -> bool:
        """Write `name` whole, or not at all; False if the name is taken."""
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self._directory, prefix=".", suffix=".tmp", delete=False
        ) as file:
            file.write(text)
        temporary = Path(file.name)
        try:
            os.link(temporary, self._directory / name)
        except FileExistsError:
            return False
        finally:
            temporary.unlink()
        return True


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
