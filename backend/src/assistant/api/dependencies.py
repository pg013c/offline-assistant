"""Services for route handlers. The composition root puts them on `app.state` (PY-21)."""

from typing import cast

from fastapi import Request

from assistant.services.documents import DocumentService


def get_document_service(request: Request) -> DocumentService:
    return cast(DocumentService, request.app.state.document_service)
