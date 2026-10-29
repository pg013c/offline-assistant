"""Plain text and Markdown, read without any model."""

from assistant.domain.documents import ParsedDocument


class TextDocumentParser:
    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        raise NotImplementedError
