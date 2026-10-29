"""Documents and their chunks: identity and splitting."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePath

DOCUMENT_ID_LENGTH = 16
_BLANK_LINES = re.compile(r"\n\s*\n")


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    title: str
    filename: str
    chunk_count: int


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    position: int
    text: str


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
