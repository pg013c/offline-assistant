from datetime import UTC, datetime

import pytest

from assistant.domain.documents import ChunkLocation
from assistant.domain.notes import Note, NoteSource, note_id, render, wants_note

CREATED = datetime(2026, 10, 30, 9, 15, 7, tzinfo=UTC)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Deployer duties", "20261030-091507-deployer-duties"),
        ("Obowiązki administratora: art. 33", "20261030-091507-obowiazki-administratora-art-33"),
        ("../../etc/passwd", "20261030-091507-etc-passwd"),
        ("/absolute/path.md", "20261030-091507-absolute-path-md"),
        ("???", "20261030-091507-note"),
        ("x" * 200, "20261030-091507-" + "x" * 60),
    ],
)
def test_a_note_id_is_the_time_and_a_safe_slug_of_its_title(title: str, expected: str) -> None:
    assert note_id(title, CREATED) == expected


def test_a_note_renders_as_markdown_with_its_sources() -> None:
    note = Note(
        id="20261030-091507-deployer-duties",
        title="Deployer duties",
        content="- Use the system as instructed [1]\n- Keep the logs [2]",
        sources=(
            NoteSource(
                number=1,
                document_title="AI Act (EN)",
                location=ChunkLocation(article="26", paragraph="1", page=71),
                chunk_id="ai:410",
            ),
            NoteSource(
                number=2,
                document_title="AI Act (EN)",
                location=ChunkLocation(article="26", paragraph="6"),
                chunk_id="ai:415",
            ),
        ),
        created=CREATED,
    )

    assert render(note) == (
        "# Deployer duties\n\n"
        "- Use the system as instructed [1]\n- Keep the logs [2]\n\n"
        "## Sources\n\n"
        "- [1] AI Act (EN), Art. 26(1), p. 71 (chunk ai:410)\n"
        "- [2] AI Act (EN), Art. 26(6) (chunk ai:415)\n\n"
        "Saved 2026-10-30 09:15 UTC by the Offline Assistant.\n"
    )


@pytest.mark.parametrize(
    "question",
    [
        "Make a checklist of a deployer's duties under Article 26 and save it as a note.",
        "Save a checklist of the controller's duties after a breach.",
        "Please store a note with the transparency obligations.",
        "Zapisz jako notatkę listę obowiązków administratora z art. 33 RODO.",
        "Zachowaj listę kontrolną obowiązków dostawcy.",
        "Zapisz notatkę o karach z art. 83.",
    ],
)
def test_a_question_asking_to_save_a_note_or_checklist_wants_one(question: str) -> None:
    assert wants_note(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "What does Article 26 say about notes?",
        "Make a checklist of the duties under Article 26.",
        "Note that Article 6 applies; what follows from it?",
        "Save time: what does Article 5 prohibit?",
        "Jakie obowiązki ma administrator?",
        "Co to jest lista kontrolna w RODO?",
    ],
)
def test_other_questions_want_no_note(question: str) -> None:
    assert wants_note(question) is False
