"""Documents and their chunks: identity and splitting."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Literal

DOCUMENT_ID_LENGTH = 16
MAX_CHUNK_CHARS = 2000
_BLANK_LINES = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    title: str
    filename: str
    chunk_count: int


@dataclass(frozen=True, slots=True)
class ChunkLocation:
    """Where a chunk sits in its document; parts the document does not have are empty."""

    heading_path: tuple[str, ...] = ()
    article: str | None = None
    paragraph: str | None = None
    page: int | None = None


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    position: int
    text: str
    location: ChunkLocation = field(default_factory=ChunkLocation)


type BlockKind = Literal["heading", "paragraph", "list_item", "table"]


@dataclass(frozen=True, slots=True)
class Block:
    """One piece of a parsed document, in reading order."""

    kind: BlockKind
    text: str
    page: int | None = None
    # Heading depth, 1 for the top level; None for other kinds.
    level: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """A document as a parser reads it: its blocks in reading order."""

    page_count: int | None
    blocks: tuple[Block, ...]


def document_id_for(content: str) -> str:
    """A stable id derived from the content, so identical uploads get the same id."""
    return hashlib.sha256(content.encode()).hexdigest()[:DOCUMENT_ID_LENGTH]


def title_from_filename(filename: str) -> str:
    """A readable title: the filename without its extension."""
    return PurePath(filename).stem


def split_into_chunks(document_id: str, text: str) -> list[Chunk]:
    """Split text into chunks at blank lines."""
    pieces = (piece.strip() for piece in _BLANK_LINES.split(text))
    return [
        Chunk(
            id=f"{document_id}:{position}", document_id=document_id, position=position, text=piece
        )
        for position, piece in enumerate(piece for piece in pieces if piece)
    ]


def chunk_document(
    document_id: str, parsed: ParsedDocument, max_chars: int = MAX_CHUNK_CHARS
) -> list[Chunk]:
    """Split a parsed document into chunks along its structure.

    Each paragraph is a chunk, with the list items that follow it; a table is one chunk;
    headings only set the location. Text longer than `max_chars` is split at sentence
    boundaries, or between words when a sentence alone is too long; tables never are.
    """
    pieces: list[tuple[str, ChunkLocation]] = []
    headings: list[tuple[int, str]] = []
    lines: list[str] = []
    location = ChunkLocation()

    def flush() -> None:
        if lines:
            pieces.extend((part, location) for part in _within_limit("\n".join(lines), max_chars))
            lines.clear()

    for block in parsed.blocks:
        text = block.text.strip()
        if not text:
            continue
        if block.kind == "heading":
            flush()
            level = block.level or 1
            headings = [*(entry for entry in headings if entry[0] < level), (level, text)]
            continue
        if block.kind == "list_item" and lines:
            lines.append(text)
            continue
        flush()
        location = ChunkLocation(
            heading_path=tuple(title for _, title in headings), page=block.page
        )
        if block.kind == "table":
            pieces.append((text, location))
        else:
            lines.append(text)
    flush()

    return [
        Chunk(
            id=f"{document_id}:{position}",
            document_id=document_id,
            position=position,
            text=text,
            location=location,
        )
        for position, (text, location) in enumerate(pieces)
    ]


def _within_limit(text: str, max_chars: int) -> list[str]:
    """Text in parts of at most `max_chars`, split at sentence ends, else between words."""
    if len(text) <= max_chars:
        return [text]
    units: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        units.extend([sentence] if len(sentence) <= max_chars else sentence.split())
    parts: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}" if current else unit
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            parts.append(current)
            current = unit
    parts.append(current)
    return parts
