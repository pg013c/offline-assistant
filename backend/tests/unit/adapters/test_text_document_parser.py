import pytest

from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.documents import Block
from assistant.domain.errors import DocumentUnreadable


def parse(text: str) -> tuple[Block, ...]:
    return TextDocumentParser().parse("notes.md", text.encode()).blocks


def test_blank_lines_separate_paragraphs() -> None:
    blocks = parse("First paragraph.\nSame paragraph.\n\n\nSecond paragraph.\n")

    assert blocks == (
        Block(kind="paragraph", text="First paragraph.\nSame paragraph."),
        Block(kind="paragraph", text="Second paragraph."),
    )


def test_markdown_headings_are_headings_with_their_level() -> None:
    blocks = parse("# Policy\nIntro text.\n\n## Scope\n\nScope text.")

    assert blocks == (
        Block(kind="heading", text="Policy", level=1),
        Block(kind="paragraph", text="Intro text."),
        Block(kind="heading", text="Scope", level=2),
        Block(kind="paragraph", text="Scope text."),
    )


def test_plain_text_has_no_pages() -> None:
    parsed = TextDocumentParser().parse("notes.txt", b"Text.")

    assert parsed.page_count is None
    assert parsed.blocks[0].page is None


def test_invalid_utf8_names_the_problem() -> None:
    with pytest.raises(DocumentUnreadable, match="UTF-8"):
        TextDocumentParser().parse("notes.txt", b"\xff\xfe")
