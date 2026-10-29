"""Chooses a parser by file extension: plain text and Markdown, or everything else."""

from pathlib import PurePath

from assistant.domain.documents import ParsedDocument
from assistant.ports.document_parser import DocumentParser

TEXT_EXTENSIONS = frozenset({".txt", ".md"})


class RoutingDocumentParser:
    def __init__(self, text: DocumentParser, rich: DocumentParser) -> None:
        self._text = text
        self._rich = rich

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        if PurePath(filename).suffix.lower() in TEXT_EXTENSIONS:
            return self._text.parse(filename, content)
        return self._rich.parse(filename, content)
