"""Mapping of domain errors to HTTP responses, in one place (PY-22)."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from assistant.api.schemas import ErrorDetail, ErrorResponse
from assistant.domain.errors import (
    DocumentNotFound,
    DocumentRejected,
    FileTooLarge,
    NoteNotFound,
    NotUtf8Text,
    RerankerOff,
    UnknownModel,
    UnsupportedFileType,
)

_DOCUMENT_REJECTIONS: dict[type, tuple[int, str]] = {
    UnsupportedFileType: (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file_type"),
    FileTooLarge: (status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large"),
    NotUtf8Text: (status.HTTP_422_UNPROCESSABLE_CONTENT, "not_utf8_text"),
}


_GENERIC_REJECTION = (status.HTTP_422_UNPROCESSABLE_CONTENT, "document_rejected")


def _rejection_status(error: Exception) -> tuple[int, str]:
    """The mapping of the closest class in the error's hierarchy that has one."""
    for cls in type(error).__mro__:
        if cls in _DOCUMENT_REJECTIONS:
            return _DOCUMENT_REJECTIONS[cls]
    return _GENERIC_REJECTION


async def _document_rejected(_: Request, error: Exception) -> JSONResponse:
    status_code, code = _rejection_status(error)
    body = ErrorResponse(code=code, message=str(error))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def _document_not_found(_: Request, error: Exception) -> JSONResponse:
    body = ErrorResponse(code="document_not_found", message=f"No document has the id {error}.")
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body.model_dump())


async def _note_not_found(_: Request, error: Exception) -> JSONResponse:
    body = ErrorResponse(code="note_not_found", message=f"No note has the id {error}.")
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body.model_dump())


async def _unknown_model(_: Request, error: Exception) -> JSONResponse:
    body = ErrorResponse(code="unknown_model", message=str(error))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump()
    )


async def _reranker_off(_: Request, __: Exception) -> JSONResponse:
    body = ErrorResponse(
        code="reranker_off",
        message="Reranking was asked for, but the server runs with ASSISTANT_RERANKER=off.",
    )
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=body.model_dump())


async def _invalid_request(_: Request, error: Exception) -> JSONResponse:
    issues = error.errors() if isinstance(error, RequestValidationError) else []
    body = ErrorResponse(
        code="invalid_request",
        message="The request is not valid.",
        details=[
            ErrorDetail(
                field=".".join(str(part) for part in issue["loc"]),
                message=str(issue["msg"]),
            )
            for issue in issues
        ],
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump()
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install the handlers for every error the API can report."""
    app.add_exception_handler(DocumentRejected, _document_rejected)
    app.add_exception_handler(DocumentNotFound, _document_not_found)
    app.add_exception_handler(NoteNotFound, _note_not_found)
    app.add_exception_handler(RerankerOff, _reranker_off)
    app.add_exception_handler(UnknownModel, _unknown_model)
    app.add_exception_handler(RequestValidationError, _invalid_request)
