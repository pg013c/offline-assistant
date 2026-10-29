import pytest

from assistant.adapters.fakes.document_parser import FakeDocumentParser
from assistant.adapters.routing_parser import RoutingDocumentParser
from assistant.domain.documents import Block, ParsedDocument


def only(text: str) -> ParsedDocument:
    return ParsedDocument(page_count=None, blocks=(Block(kind="paragraph", text=text),))


@pytest.fixture
def parser() -> RoutingDocumentParser:
    return RoutingDocumentParser(
        text=FakeDocumentParser(only("text")), rich=FakeDocumentParser(only("rich"))
    )


@pytest.mark.parametrize("filename", ["notes.txt", "README.MD"])
def test_text_files_go_to_the_text_parser(parser: RoutingDocumentParser, filename: str) -> None:
    assert parser.parse(filename, b"x").blocks[0].text == "text"


@pytest.mark.parametrize(
    "filename", ["act.pdf", "policy.docx", "scan.PNG", "photo.jpg", "photo.jpeg"]
)
def test_other_files_go_to_the_rich_parser(parser: RoutingDocumentParser, filename: str) -> None:
    assert parser.parse(filename, b"x").blocks[0].text == "rich"
