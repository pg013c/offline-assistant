"""DocumentParser for tests: returns a given document, or fails for given filenames."""

from collections.abc import Mapping

from assistant.domain.documents import ParsedDocument


class FakeDocumentParser:
    def __init__(
        self, document: ParsedDocument, unreadable: Mapping[str, str] | None = None
    ) -> None:
        self._document = document
        self._unreadable = dict(unreadable or {})

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        raise NotImplementedError
