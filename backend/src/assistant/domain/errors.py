"""Reasons a request is rejected, independent of how they are reported."""


class DocumentRejected(Exception):
    """An uploaded file cannot become a document."""


class UnsupportedFileType(DocumentRejected):
    """Only plain text and Markdown are accepted (F-01)."""


class FileTooLarge(DocumentRejected):
    """The file exceeds the upload size limit."""


class NotUtf8Text(DocumentRejected):
    """The file is not valid UTF-8 text."""
