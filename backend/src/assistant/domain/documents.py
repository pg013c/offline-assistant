"""Documents and their chunks: identity and splitting."""

import hashlib
import re
from dataclasses import dataclass, field, replace
from pathlib import PurePath
from typing import Literal

DOCUMENT_ID_LENGTH = 16
MAX_CHUNK_CHARS = 2000
# A sentence: text up to and including its end mark, or to the end of the text.
_SENTENCE = re.compile(r"\S.*?(?:[.!?](?=\s|$)|$)", re.DOTALL)
_WORD = re.compile(r"\S+")


type DocumentStatus = Literal["processing", "ready", "failed"]


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    title: str
    filename: str
    chunk_count: int
    status: DocumentStatus
    page_count: int | None = None
    failure_reason: str | None = None


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


def document_id_for(content: bytes) -> str:
    """A stable id derived from the uploaded bytes, so identical uploads get the same id."""
    return hashlib.sha256(content).hexdigest()[:DOCUMENT_ID_LENGTH]


def title_from_filename(filename: str) -> str:
    """A readable title: the filename without its extension."""
    return PurePath(filename).stem


def chunk_document(
    document_id: str, parsed: ParsedDocument, max_chars: int = MAX_CHUNK_CHARS
) -> list[Chunk]:
    """Split a parsed document into chunks along its structure.

    Each paragraph is a chunk, with the list items that follow it; a table is one chunk;
    headings only set the location. In legal texts, each numbered paragraph of an article
    is a chunk with everything up to the next one, and no chunk crosses an article. Text
    longer than `max_chars` is split at sentence boundaries, or between words when a
    sentence alone is too long; tables never are.
    """
    chunker = _Chunker(max_chars)
    for block in parsed.blocks:
        chunker.add(block)
    return [
        Chunk(
            id=f"{document_id}:{position}",
            document_id=document_id,
            position=position,
            text=text,
            location=location,
        )
        for position, (text, location) in enumerate(chunker.finish())
    ]


# "Article 6", "Artykuł 6", "Art. 6a"; a heading may continue with the title.
_ARTICLE = re.compile(r"^(?:Article|Artykuł|Art\.)\s+(\d+[a-z]*)\b", re.IGNORECASE)
_NUMBERED_PARAGRAPH = re.compile(r"^(\d+[a-z]?)\.\s")


class _Chunker:
    """Walks blocks in reading order, keeping track of headings, article and paragraph."""

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars
        self._pieces: list[tuple[str, ChunkLocation]] = []
        self._headings: list[tuple[int, str]] = []
        # The text of the chunk being built, one entry per block, with the block's page.
        self._lines: list[tuple[str, int | None]] = []
        self._location = ChunkLocation()
        self._article: str | None = None
        self._article_level = 1
        self._paragraph: str | None = None
        # True between an article heading and its first content: the next heading is its title.
        self._expecting_title = False

    def add(self, block: Block) -> None:
        text = block.text.strip()
        if not text:
            return
        article = _ARTICLE.match(text)
        if article and (block.kind == "heading" or article.end() == len(text)):
            self._start_article(article.group(1), text, block.level)
        elif block.kind == "heading":
            self._heading(text, block.level or 1)
        else:
            self._content(block.kind, text, block.page)

    def finish(self) -> list[tuple[str, ChunkLocation]]:
        self._flush()
        return self._pieces

    def _start_article(self, number: str, text: str, level: int | None) -> None:
        self._flush()
        if level is None:
            level = self._article_level if self._article else len(self._headings) + 1
        self._set_heading(level, text)
        self._article, self._article_level, self._paragraph = number, level, None
        self._expecting_title = True

    def _heading(self, text: str, level: int) -> None:
        if self._expecting_title:
            self._headings.append((level, text))
            self._expecting_title = False
            return
        self._flush()
        self._article = self._paragraph = None
        self._set_heading(level, text)

    def _set_heading(self, level: int, text: str) -> None:
        self._headings = [*(entry for entry in self._headings if entry[0] < level), (level, text)]

    def _content(self, kind: BlockKind, text: str, page: int | None) -> None:
        self._expecting_title = False
        # Parsers deliver numbered paragraphs as paragraphs or as numbered list items.
        numbered = _NUMBERED_PARAGRAPH.match(text) if self._article and kind != "table" else None
        if numbered:
            self._paragraph = numbered.group(1)
        elif kind != "table" and self._lines and (self._article or kind == "list_item"):
            # Inside an article everything up to the next numbered paragraph belongs together.
            self._lines.append((text, page))
            return
        self._flush()
        self._location = ChunkLocation(
            heading_path=tuple(title for _, title in self._headings),
            article=self._article,
            paragraph=self._paragraph,
            page=page,
        )
        if kind == "table":
            self._pieces.append((text, self._location))
        else:
            self._lines.append((text, page))

    def _flush(self) -> None:
        if not self._lines:
            return
        joined = "\n".join(text for text, _ in self._lines)
        # Where each block starts in the joined text, so each part gets the page it starts on.
        starts: list[tuple[int, int | None]] = []
        offset = 0
        for text, page in self._lines:
            starts.append((offset, page))
            offset += len(text) + 1
        for part, start in _within_limit(joined, self._max_chars):
            page = next(page for begin, page in reversed(starts) if begin <= start)
            self._pieces.append((part, replace(self._location, page=page)))
        self._lines.clear()


def _within_limit(text: str, max_chars: int) -> list[tuple[str, int]]:
    """Text in parts of at most `max_chars`, each with its start offset in `text`.

    Splits at sentence ends, else between words; a word longer than the limit is cut.
    """
    if len(text) <= max_chars:
        return [(text, 0)]
    units: list[tuple[str, int]] = []
    for sentence in _SENTENCE.finditer(text):
        if len(sentence.group()) <= max_chars:
            units.append((sentence.group(), sentence.start()))
            continue
        for word in _WORD.finditer(sentence.group()):
            start = sentence.start() + word.start()
            units.extend(
                (word.group()[cut : cut + max_chars], start + cut)
                for cut in range(0, len(word.group()), max_chars)
            )
    parts: list[tuple[str, int]] = []
    current, current_start = "", 0
    for unit, start in units:
        candidate = f"{current} {unit}" if current else unit
        if not current:
            current, current_start = unit, start
        elif len(candidate) <= max_chars:
            current = candidate
        else:
            parts.append((current, current_start))
            current, current_start = unit, start
    parts.append((current, current_start))
    return parts
