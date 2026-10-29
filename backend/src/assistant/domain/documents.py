"""Documents and their chunks: identity and splitting."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Literal

DOCUMENT_ID_LENGTH = 16
MAX_CHUNK_CHARS = 2000
_BLANK_LINES = re.compile(r"\n\s*\n")


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
    """Split a parsed document into chunks along its structure."""
    raise NotImplementedError
