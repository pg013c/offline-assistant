"""Chooses a parser by file extension."""

from assistant.domain.documents import ParsedDocument
from assistant.ports.document_parser import DocumentParser


class RoutingDocumentParser:
    def __init__(self, text: DocumentParser, rich: DocumentParser) -> None:
        self._text = text
        self._rich = rich

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        raise NotImplementedError
