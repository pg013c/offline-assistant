from typing import Annotated

from fastapi import APIRouter, Depends, status

from assistant.api.dependencies import get_note_service
from assistant.api.schemas import (
    CitationLocation,
    ErrorResponse,
    NoteDetail,
    NoteSourceResponse,
    NoteSummary,
)
from assistant.domain.notes import render
from assistant.services.notes import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])

Notes = Annotated[NoteService, Depends(get_note_service)]


@router.get("")
def list_notes(notes: Notes) -> list[NoteSummary]:
    """The notes the agent saved, newest first."""
    return [
        NoteSummary(id=note.id, title=note.title, created=note.created)
        for note in notes.list_notes()
    ]


@router.get("/{note_id}", responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}})
def get_note(note_id: str, notes: Notes) -> NoteDetail:
    """One note: its content, the passages it cites and the Markdown file's text."""
    note = notes.get(note_id)
    return NoteDetail(
        id=note.id,
        title=note.title,
        created=note.created,
        content=note.content,
        sources=[
            NoteSourceResponse(
                number=source.number,
                document_title=source.document_title,
                chunk_id=source.chunk_id,
                location=CitationLocation(
                    heading_path=list(source.location.heading_path),
                    article=source.location.article,
                    paragraph=source.location.paragraph,
                    page=source.location.page,
                ),
            )
            for source in note.sources
        ],
        markdown=render(note),
    )
