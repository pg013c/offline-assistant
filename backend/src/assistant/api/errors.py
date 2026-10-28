"""Mapping of domain errors to HTTP responses, in one place (PY-22)."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from assistant.api.schemas import ErrorResponse
from assistant.domain.errors import (
    DocumentRejected,
    FileTooLarge,
    NotUtf8Text,
    UnsupportedFileType,
)

_DOCUMENT_REJECTIONS: dict[type[DocumentRejected], tuple[int, str]] = {
    UnsupportedFileType: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type"),
    FileTooLarge: (status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large"),
    NotUtf8Text: (status.HTTP_422_UNPROCESSABLE_CONTENT, "not_utf8_text"),
}


async def _document_rejected(_: Request, error: Exception) -> JSONResponse:
    status_code, code = _DOCUMENT_REJECTIONS[type(error)]  # type: ignore[index]
    body = ErrorResponse(code=code, message=str(error))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    """Install the handlers for every domain error the API can report."""
    app.add_exception_handler(DocumentRejected, _document_rejected)
