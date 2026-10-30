"""The tools the agent may call: search, one article, two articles side by side (F-07).

Every result reaches the model as data: numbered passage blocks, or a sentence it can act on.
A mistake in the arguments is a result too, so the model can correct it (AI-21).
"""

import asyncio
import re
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime

from assistant.domain.answers import markers, statements
from assistant.domain.documents import Chunk, Document, indexed_text
from assistant.domain.notes import Note, NoteSource, note_id
from assistant.domain.tools import (
    CompareArguments,
    GetArticleArguments,
    PassageLedger,
    SaveNoteArguments,
    SearchDocumentsArguments,
    ToolCall,
    ToolSpec,
    neutralised,
)
from assistant.ports.document_store import DocumentStore
from assistant.ports.note_store import NoteStore
from assistant.services.questions import CANDIDATES, RERANK_CANDIDATES, QuestionService

# Passages a tool returns at most: a search, one article, each article of a comparison.
SEARCH_CAP = 5
ARTICLE_CAP = 12
COMPARE_CAP = 6

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="search_documents",
        description=(
            "Search the uploaded documents for passages relevant to a query. Optionally keep "
            "to one document, named by its title."
        ),
        arguments=SearchDocumentsArguments,
    ),
    ToolSpec(
        name="get_article",
        description="The full text of one article of a document, e.g. GDPR (EN), article 17.",
        arguments=GetArticleArguments,
    ),
    ToolSpec(
        name="compare",
        description="Two articles side by side, from the same or different documents.",
        arguments=CompareArguments,
    ),
)

_ARTICLE_NUMBER = re.compile(r"\d+[a-z]?", re.IGNORECASE)


# Offered only when the user asks to save a note (F-07a); the one tool that writes (AI-11).
SAVE_NOTE = ToolSpec(
    name="save_note",
    description=(
        "Save a note or checklist for the user in the local notes. Every sentence or list item "
        "of the content ends with the numbers of the passages it rests on, like [1]."
    ),
    arguments=SaveNoteArguments,
)


class _ToolError(Exception):
    """The arguments name something that does not exist; the message goes to the model."""


class DocumentTools:
    """Runs the agent's tool calls against the stored and indexed documents."""

    def __init__(
        self,
        questions: QuestionService,
        store: DocumentStore,
        notes: NoteStore | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._questions = questions
        self._store = store
        self._notes = notes
        self._clock = clock

    async def run(self, call: ToolCall, ledger: PassageLedger) -> str:
        """The tool's result as the model reads it; passages are numbered in `ledger`."""
        try:
            match call.arguments:
                case SearchDocumentsArguments() as arguments:
                    return await self._search(arguments, ledger)
                case GetArticleArguments() as arguments:
                    return await self._article(
                        arguments.document, arguments.number, ARTICLE_CAP, ledger
                    )
                case SaveNoteArguments() as arguments if self._notes is not None:
                    return await self._save_note(arguments, ledger, self._notes)
                case CompareArguments(a=a, b=b):
                    first = await self._article(a.document, a.number, COMPARE_CAP, ledger)
                    second = await self._article(b.document, b.number, COMPARE_CAP, ledger)
                    return f"{first}\n\n{second}"
                case _:
                    return f"Error: there is no tool {call.name}."
        except _ToolError as error:
            return f"Error: {error}"

    async def document_titles(self) -> list[str]:
        """The titles of the stored documents, in order, for the agent's prompt."""
        documents = await asyncio.to_thread(self._store.list_documents)
        return [document.title for document in _by_title(documents)]

    async def _save_note(
        self, arguments: SaveNoteArguments, ledger: PassageLedger, notes: NoteStore
    ) -> str:
        """Saves the note when every line cites passages of this run; the service, not the
        model, turns the markers into the note's sources (FR-11)."""
        if ledger.saved_notes:
            raise _ToolError(
                f"a note was already saved in this run ({ledger.saved_notes[0].id}); "
                "do not save another"
            )
        cited = list(dict.fromkeys(markers(arguments.content)))
        for number in cited:
            if not 1 <= number <= len(ledger):
                raise _ToolError(
                    f"passage {number} was not gathered in this run; "
                    f"cite passages 1 to {len(ledger)}"
                )
        if not cited:
            raise _ToolError(
                "the note cites no passage; end every sentence and list item with the numbers "
                "of the passages it rests on, like [1]"
            )
        lines = statements(arguments.content)
        for position, statement in enumerate(lines):
            if markers(statement) or _opens_list(statement, lines[position + 1 :]):
                continue
            kind = "line" if _is_item(statement) else "sentence"
            raise _ToolError(
                f'the {kind} "{statement}" cites no passage; end every sentence and list '
                "item with the numbers of the passages it rests on, like [1]"
            )
        created = self._clock()
        sources = []
        for number in sorted(cited):
            chunk = ledger.passages[number - 1]
            document = await asyncio.to_thread(self._store.get, chunk.document_id)
            sources.append(
                NoteSource(
                    number=number,
                    document_title=document.title if document else chunk.document_id,
                    location=chunk.location,
                    chunk_id=chunk.id,
                )
            )
        note = Note(
            id=note_id(arguments.title, created),
            title=arguments.title,
            content=arguments.content,
            sources=tuple(sources),
            created=created,
        )
        saved = await asyncio.to_thread(notes.save, note)
        ledger.saved(replace(note, id=saved))
        return f"Saved note {saved}."

    async def _search(self, arguments: SearchDocumentsArguments, ledger: PassageLedger) -> str:
        document = await self._document(arguments.document) if arguments.document else None
        # Keeping to one document filters the candidates, so more of them are fetched.
        found = await self._questions.search(
            arguments.query, RERANK_CANDIDATES if document else CANDIDATES
        )
        relevant = [
            passage
            for passage in found
            if passage.similarity >= self._questions.min_similarity
            and (document is None or passage.chunk.document_id == document.id)
        ][:SEARCH_CAP]
        if not relevant:
            return f'No passage above the relevance threshold was found for "{arguments.query}".'
        return _blocks([(passage.chunk, passage.document_title) for passage in relevant], ledger)

    async def _article(self, name: str, number: str, cap: int, ledger: PassageLedger) -> str:
        document = await self._document(name)
        # The store reads files; keep that off the event loop.
        stored = await asyncio.to_thread(self._store.load_chunks, document.id)
        label = _ARTICLE_NUMBER.search(number)
        wanted = label.group().lower() if label else number
        chunks = sorted(
            (chunk for chunk in stored if (chunk.location.article or "").lower() == wanted),
            key=lambda chunk: chunk.position,
        )
        if not chunks:
            raise _ToolError(f"{document.title} has no article {number}.")
        result = _blocks([(chunk, document.title) for chunk in chunks[:cap]], ledger)
        if len(chunks) > cap:
            result += f"\n\n({len(chunks) - cap} more passages of this article are not shown.)"
        return result

    async def _document(self, name: str) -> Document:
        documents = await asyncio.to_thread(self._store.list_documents)
        wanted = name.strip().lower()
        for document in documents:
            if wanted in (document.id.lower(), document.title.lower()):
                return document
        titles = ", ".join(f'"{document.title}"' for document in _by_title(documents))
        raise _ToolError(f'there is no document "{name}". The documents are: {titles}.')


def _is_item(line: str) -> bool:
    return line[:1] in "-*•" or line[:1].isdigit()


def _opens_list(line: str, rest: Sequence[str]) -> bool:
    """Whether a line ending in a colon introduces the list item after it; that line states
    nothing itself and needs no marker."""
    return line.endswith(":") and bool(rest) and _is_item(rest[0])


def _by_title(documents: Sequence[Document]) -> list[Document]:
    return sorted(documents, key=lambda document: document.title)


def _blocks(passages: Sequence[tuple[Chunk, str]], ledger: PassageLedger) -> str:
    """Numbered passage blocks for the chunks the ledger takes, and a note for any it does not."""
    blocks: list[str] = []
    left_out = 0
    for chunk, title in passages:
        number = ledger.number(chunk)
        if number is None:
            left_out += 1
        else:
            blocks.append(_block(number, chunk, title))
    if left_out:
        blocks.append(
            f"(The answer can rest on at most {ledger.limit} passages; {left_out} more were "
            "not added. Reply ready to answer from the passages you have.)"
        )
    return "\n\n".join(blocks)


def _block(number: int, chunk: Chunk, title: str) -> str:
    article = f' article="{chunk.location.article}"' if chunk.location.article else ""
    attributes = f'number="{number}" document="{title.replace('"', "'")}"{article}'
    return f"<passage {attributes}>\n{neutralised(indexed_text(chunk))}\n</passage>"
