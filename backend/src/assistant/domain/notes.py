"""Notes the agent saves for the user (F-07a).

A note is the model's title and content, and the passages its `[n]` markers cite, which the
service turns into the note's sources. Its id is the time it was saved and a slug of its
title, so it is a plain file name that cannot leave the notes directory (AI-11).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from assistant.domain.documents import ChunkLocation

TITLE_LIMIT = 120
CONTENT_LIMIT = 20_000
_SLUG_LIMIT = 60
_NOT_SLUG = re.compile(r"[^a-z0-9]+")
# Letters ASCII folding cannot reach.
_FOLD = str.maketrans({"ł": "l", "Ł": "L"})

# A note is wanted only when the question asks to save or store one (spec decision 1).
_SAVE = re.compile(r"\b(?:save|store|zapisz\w*|zachowaj\w*)\b", re.IGNORECASE)
_NOTE = re.compile(r"\b(?:notes?|checklists?|notatk\w*|list\w* kontroln\w*)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class NoteSource:
    """A passage the note cites, by the number its markers use."""

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
    """`YYYYMMDD-HHMMSS-<slug>`: lower-case ASCII letters, digits and hyphens only."""
    folded = unicodedata.normalize("NFKD", title.translate(_FOLD))
    ascii_title = folded.encode("ascii", "ignore").decode().lower()
    slug = _NOT_SLUG.sub("-", ascii_title).strip("-")[:_SLUG_LIMIT].strip("-") or "note"
    return f"{created:%Y%m%d-%H%M%S}-{slug}"


def render(note: Note) -> str:
    """The note as the Markdown file the user opens."""
    sources = "\n".join(
        f"- [{source.number}] {_source_label(source)} (chunk {source.chunk_id})"
        for source in note.sources
    )
    return (
        f"# {note.title}\n\n{note.content}\n\n## Sources\n\n{sources}\n\n"
        f"Saved {note.created:%Y-%m-%d %H:%M} UTC by the Offline Assistant.\n"
    )


def _source_label(source: NoteSource) -> str:
    location = source.location
    parts = [source.document_title]
    if location.article:
        paragraph = f"({location.paragraph})" if location.paragraph else ""
        parts.append(f"Art. {location.article}{paragraph}")
    if location.page is not None:
        parts.append(f"p. {location.page}")
    return ", ".join(parts)


def wants_note(question: str) -> bool:
    """True when the question asks to save a note or a checklist."""
    return bool(_SAVE.search(question) and _NOTE.search(question))
