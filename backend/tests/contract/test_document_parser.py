"""Contract for the DocumentParser port; every adapter must pass it."""

from dataclasses import dataclass

import pytest

from assistant.adapters.fakes.document_parser import FakeDocumentParser
from assistant.adapters.text_document_parser import TextDocumentParser
from assistant.domain.documents import Block, ParsedDocument
from assistant.domain.errors import DocumentUnreadable
from assistant.ports.document_parser import DocumentParser


@dataclass(frozen=True)
class Case:
    parser: DocumentParser
    readable: tuple[str, bytes]
    unreadable: tuple[str, bytes]
    first_text: str


FAKE_DOCUMENT = ParsedDocument(
    page_count=1, blocks=(Block(kind="paragraph", text="Fake text.", page=1),)
)

CASES = {
    "fake": Case(
        parser=FakeDocumentParser(FAKE_DOCUMENT, unreadable={"broken.pdf": "corrupt file"}),
        readable=("any.pdf", b"%PDF"),
        unreadable=("broken.pdf", b"%PDF"),
        first_text="Fake text.",
    ),
    "text": Case(
        parser=TextDocumentParser(),
        readable=("notes.md", b"First paragraph.\n\nSecond paragraph."),
        unreadable=("notes.txt", b"\xff\xfe not utf-8 \xff"),
        first_text="First paragraph.",
    ),
}


@pytest.fixture(params=list(CASES), ids=list(CASES))
def case(request: pytest.FixtureRequest) -> Case:
    return CASES[request.param]


def test_parses_blocks_in_reading_order(case: Case) -> None:
    filename, content = case.readable

    parsed = case.parser.parse(filename, content)

    assert parsed.blocks
    assert parsed.blocks[0].text == case.first_text


def test_same_input_gives_the_same_result(case: Case) -> None:
    filename, content = case.readable

    assert case.parser.parse(filename, content) == case.parser.parse(filename, content)


def test_unreadable_content_raises_with_a_reason(case: Case) -> None:
    filename, content = case.unreadable

    with pytest.raises(DocumentUnreadable) as raised:
        case.parser.parse(filename, content)

    assert raised.value.reason
