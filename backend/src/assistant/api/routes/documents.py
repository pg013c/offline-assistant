from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from assistant.api.dependencies import get_document_service
from assistant.api.schemas import (
    ChunkSummary,
    CitationLocation,
    DocumentResponse,
    ErrorResponse,
)
from assistant.domain.documents import Document
from assistant.services.documents import MAX_UPLOAD_BYTES, DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

Documents = Annotated[DocumentService, Depends(get_document_service)]


def _response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        title=document.title,
        filename=document.filename,
        status=document.status,
        chunk_count=document.chunk_count,
        page_count=document.page_count,
        failure_reason=document.failure_reason,
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def upload_document(file: UploadFile, documents: Documents) -> DocumentResponse:
    """Upload a document to be parsed in the background; known content returns as stored.

    Accepts PDF, DOCX, PNG, JPG, plain text and Markdown. The document is listed with status
    `processing` until parsing ends with `ready` or `failed`.
    """
    # One byte past the limit is enough for the service to reject the file (GEN-42).
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    # Storing touches the disk; keep it off the event loop (PY-14).
    document = await run_in_threadpool(documents.upload, file.filename or "", content)
    return _response(document)


@router.get("")
def list_documents(documents: Documents) -> list[DocumentResponse]:
    """All uploaded documents."""
    return [_response(document) for document in documents.list_documents()]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def delete_document(document_id: str, documents: Documents) -> None:
    """Delete a document, its files and its passages from the search index."""
    await run_in_threadpool(documents.delete, document_id)


@router.post(
    "/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def reindex_document(document_id: str, documents: Documents) -> DocumentResponse:
    """Parse and index a document again; it is `processing` until it is `ready` or `failed`."""
    document = await run_in_threadpool(documents.reindex, document_id)
    return _response(document)


@router.get(
    "/{document_id}/chunks",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def list_document_chunks(document_id: str, documents: Documents) -> list[ChunkSummary]:
    """The passages of a document with their locations and text, in order."""
    return [
        ChunkSummary(
            chunk_id=chunk.id,
            position=chunk.position,
            location=CitationLocation(
                heading_path=list(chunk.location.heading_path),
                article=chunk.location.article,
                paragraph=chunk.location.paragraph,
                page=chunk.location.page,
            ),
            text=chunk.text,
        )
        for chunk in documents.chunks(document_id)
    ]
