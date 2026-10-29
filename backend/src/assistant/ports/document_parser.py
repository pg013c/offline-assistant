from typing import Protocol

from assistant.domain.documents import ParsedDocument


class DocumentParser(Protocol):
    """Reads an uploaded file into its structure: headings, paragraphs, tables and pages."""

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        """The document's blocks in reading order; raises `DocumentUnreadable` with a reason."""
        ...
