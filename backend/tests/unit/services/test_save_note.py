"""The save_note tool: the only tool that writes, and only into the notes (F-07a, AI-11)."""

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import InlineIngestionQueue
from assistant.adapters.fakes.note_store import InMemoryNoteStore
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.notes import CONTENT_LIMIT, TITLE_LIMIT, NoteSource
from assistant.domain.tools import (
    GetArticleArguments,
    PassageLedger,
    SaveNoteArguments,
    ToolCall,
)
from assistant.services.documents import DocumentService
from assistant.services.questions import QuestionService
from assistant.services.tools import SAVE_NOTE, DocumentTools

GDPR = b"""# GDPR (EN)

## Article 33

Notification of a personal data breach

1. The controller shall notify the breach within 72 hours.

2. The processor shall notify the controller without undue delay.
"""

NOW = datetime(2026, 10, 30, 9, 15, 7, tzinfo=UTC)

type Setup = tuple[DocumentTools, InMemoryNoteStore, PassageLedger]


@pytest.fixture
def setup() -> Setup:
    store = FakeDocumentStore()
    index = InMemoryChunkIndex()
    DocumentService(store, index, TextDocumentParser(), InlineIngestionQueue()).upload(
        "GDPR (EN).md", GDPR
    )
    questions = QuestionService(index, FakeExtractiveChatModel(), store, min_similarity=0)
    notes = InMemoryNoteStore()
    tools = DocumentTools(questions, store, notes=notes, clock=lambda: NOW)
    ledger = PassageLedger()
    reading = GetArticleArguments(document="GDPR (EN)", number="33")
    asyncio.run(tools.run(ToolCall(id="c0", name="get_article", arguments=reading), ledger))
    return tools, notes, ledger


def save(tools: DocumentTools, ledger: PassageLedger, title: str, content: str) -> str:
    call = ToolCall(
        id="c1", name="save_note", arguments=SaveNoteArguments(title=title, content=content)
    )
    return asyncio.run(tools.run(call, ledger))


def test_the_save_note_tool_takes_a_title_and_content() -> None:
    assert SAVE_NOTE.name == "save_note"
    assert set(SAVE_NOTE.arguments.model_json_schema()["properties"]) == {"title", "content"}


def test_a_valid_note_is_saved_with_the_passages_it_cites_as_sources(setup: Setup) -> None:
    tools, notes, ledger = setup

    result = save(
        tools,
        ledger,
        "Breach duties",
        "- Notify the authority within 72 hours [1]\n- Inform the controller [2]",
    )

    [note] = notes.list_notes()
    assert result == f"Saved note {note.id}."
    assert note.id == "20261030-091507-breach-duties"
    assert note.created == NOW
    assert note.sources == tuple(
        NoteSource(
            number=number,
            document_title="GDPR (EN)",
            location=chunk.location,
            chunk_id=chunk.id,
        )
        for number, chunk in enumerate(ledger.passages, start=1)
    )
    assert ledger.saved_notes == (note,)


def test_only_the_cited_passages_become_sources(setup: Setup) -> None:
    tools, notes, ledger = setup

    save(tools, ledger, "Breach", "Notify the authority within 72 hours [1].")

    [note] = notes.list_notes()
    assert [source.number for source in note.sources] == [1]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (
            "- Notify within 72 hours [1]\n- Inform the controller",
            'the line "- Inform the controller" cites no passage',
        ),
        (
            "Notify within 72 hours [7].",
            "passage 7 was not gathered in this run; cite passages 1 to 2",
        ),
        ("Notify within 72 hours.", "cites no passage"),
        ("Deployers must inform workers before use:", "the note cites no passage"),
        (
            "Every controller must report breaches:\nThis is done within 72 hours [1].",
            'the sentence "Every controller must report breaches:" cites no passage',
        ),
    ],
)
def test_content_with_an_uncited_line_or_an_unknown_passage_is_an_error_and_nothing_is_saved(
    setup: Setup, content: str, reason: str
) -> None:
    tools, notes, ledger = setup

    result = save(tools, ledger, "Breach", content)

    assert result.startswith("Error:")
    assert reason in result
    assert notes.list_notes() == []
    assert ledger.saved_notes == ()


@pytest.mark.parametrize(
    ("title", "content"),
    [
        ("x" * (TITLE_LIMIT + 1), "Notify [1]."),
        ("", "Notify [1]."),
        ("Breach", "x" * (CONTENT_LIMIT + 1)),
        ("Breach", " "),
    ],
)
def test_titles_and_contents_out_of_bounds_fail_argument_validation(
    title: str, content: str
) -> None:
    with pytest.raises(ValidationError):
        SaveNoteArguments(title=title, content=content)


def test_without_a_note_store_there_is_no_save_note_tool(setup: Setup) -> None:
    _, _, ledger = setup
    store = FakeDocumentStore()
    questions = QuestionService(InMemoryChunkIndex(), FakeExtractiveChatModel(), store, 0)
    read_only = DocumentTools(questions, store)

    result = save(read_only, ledger, "Breach", "Notify [1].")

    assert result == "Error: there is no tool save_note."


def test_a_line_that_introduces_a_list_with_a_colon_needs_no_marker(setup: Setup) -> None:
    tools, notes, ledger = setup

    result = save(
        tools,
        ledger,
        "Breach duties",
        "The controller's duties under Article 33 include:\n- Notify within 72 hours [1]",
    )

    assert result.startswith("Saved note ")
    assert len(notes.list_notes()) == 1


def test_the_schema_sent_to_the_model_has_no_bound_a_server_grammar_cannot_take() -> None:
    content = SAVE_NOTE.arguments.model_json_schema()["properties"]["content"]

    assert "pattern" not in content
    assert "maxLength" not in content


def test_a_run_saves_one_note_and_refuses_a_second(setup: Setup) -> None:
    tools, notes, ledger = setup
    save(tools, ledger, "Breach", "Notify within 72 hours [1].")

    result = save(tools, ledger, "Another", "Inform the controller [2].")

    assert result.startswith("Error: a note was already saved in this run")
    assert len(notes.list_notes()) == 1
