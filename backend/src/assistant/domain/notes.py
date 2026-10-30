"""Notes the agent saves for the user (F-07a)."""

from dataclasses import dataclass, field
from datetime import datetime

from assistant.domain.documents import ChunkLocation


@dataclass(frozen=True, slots=True)
class NoteSource:
    number: int
    document_title: str
    location: ChunkLocation = field(default_factory=ChunkLocation)
    chunk_id: str = ""


@dataclass(frozen=True, slots=True)
class Note:
    id: str
    title: str
    content: str
    sources: tuple[NoteSource, ...]
    created: datetime


def note_id(title: str, created: datetime) -> str:
    raise NotImplementedError


def render(note: Note) -> str:
    raise NotImplementedError


def wants_note(question: str) -> bool:
    raise NotImplementedError
