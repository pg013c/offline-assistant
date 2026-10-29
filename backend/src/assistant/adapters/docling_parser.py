"""PDF, DOCX and images through Docling, with Tesseract for OCR (ADR 0015)."""

from pathlib import Path

from assistant.domain.documents import ParsedDocument


class ParserNotReady(Exception):
    """A model or tool the parser needs is missing; the message says how to install it."""


class DoclingDocumentParser:
    def __init__(
        self, models_dir: Path, max_pages: int = 500, tesseract: str = "tesseract"
    ) -> None:
        raise NotImplementedError

    @staticmethod
    def ensure_ready(models_dir: Path, tesseract: str = "tesseract") -> None:
        """Raise `ParserNotReady` unless the models and Tesseract with `eng` and `pol` exist."""
        raise NotImplementedError

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        raise NotImplementedError
