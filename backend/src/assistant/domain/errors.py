"""Reasons a request is rejected, independent of how they are reported."""


class DocumentRejected(Exception):
    """An uploaded file cannot become a document."""


class UnsupportedFileType(DocumentRejected):
    """The file is not one of the accepted types: PDF, DOCX, PNG, JPG, text or Markdown."""


class FileTooLarge(DocumentRejected):
    """The file exceeds the upload size limit."""


class NotUtf8Text(DocumentRejected):
    """The file is not valid UTF-8 text."""


class DocumentUnreadable(Exception):
    """A stored file could not be parsed; the reason is shown to the user."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
