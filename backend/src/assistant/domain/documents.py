"""Documents and their chunks: identity and splitting."""

from dataclasses import dataclass


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
    raise NotImplementedError


def title_from_filename(filename: str) -> str:
    """A readable title: the filename without its extension."""
    raise NotImplementedError


def split_into_chunks(document_id: str, text: str) -> list[Chunk]:
    """Split text into chunks at blank lines."""
    raise NotImplementedError
