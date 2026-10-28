from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status

from assistant.api.dependencies import get_document_service
from assistant.api.schemas import DocumentResponse, ErrorResponse
from assistant.domain.documents import Document
from assistant.services.documents import MAX_UPLOAD_BYTES, DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

Documents = Annotated[DocumentService, Depends(get_document_service)]


def _response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        title=document.title,
        filename=document.filename,
        chunk_count=document.chunk_count,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def upload_document(file: UploadFile, documents: Documents) -> DocumentResponse:
    """Upload a plain-text or Markdown document; known content returns the stored document."""
    # One byte past the limit is enough for the service to reject the file (GEN-42).
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    return _response(documents.upload(file.filename or "", content))


@router.get("")
def list_documents(documents: Documents) -> list[DocumentResponse]:
    """All uploaded documents."""
    return [_response(document) for document in documents.list_documents()]
