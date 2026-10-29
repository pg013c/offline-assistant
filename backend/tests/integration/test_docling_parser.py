"""The Docling parser on real files (ADR 0015). Needs `make models` and Tesseract."""

import os
from pathlib import Path

import pytest

from assistant.adapters.docling_parser import DoclingDocumentParser, ParserNotReady
from assistant.domain.documents import Chunk, chunk_document
from assistant.domain.errors import DocumentUnreadable

pytestmark = pytest.mark.integration

DOCUMENTS = Path(__file__).parents[1] / "fixtures" / "documents"
MODELS_DIR = Path(
    os.environ.get("ASSISTANT_MODELS_DIR", Path(__file__).parents[3] / "data" / "models")
)


@pytest.fixture(scope="module")
def parser() -> DoclingDocumentParser:
    # Loading the models takes seconds; one parser serves the whole module.
    DoclingDocumentParser.ensure_ready(MODELS_DIR)
    return DoclingDocumentParser(MODELS_DIR)


def chunks_of(parser: DoclingDocumentParser, filename: str) -> list[Chunk]:
    content = (DOCUMENTS / filename).read_bytes()
    return chunk_document("doc", parser.parse(filename, content))


def article_paragraphs(chunks: list[Chunk], article: str) -> list[str | None]:
    return [chunk.location.paragraph for chunk in chunks if chunk.location.article == article]


@pytest.mark.parametrize(
    ("filename", "heading", "phrase"),
    [
        ("ai-act-art6-en.pdf", "Article 6", "Irrespective of whether an AI system"),
        ("ai-act-art6-pl.pdf", "Artykuł 6", "Bez względu na to, czy system AI"),
    ],
)
def test_each_numbered_paragraph_of_article_6_is_a_chunk_with_its_page(
    parser: DoclingDocumentParser, filename: str, heading: str, phrase: str
) -> None:
    chunks = chunks_of(parser, filename)

    assert article_paragraphs(chunks, "6") == [str(number) for number in range(1, 9)]
    first = next(chunk for chunk in chunks if chunk.location.article == "6")
    assert heading in first.location.heading_path
    assert first.location.page == 1
    assert phrase in first.text
    assert "(a)" in first.text or "a)" in first.text
    third = next(
        chunk
        for chunk in chunks
        if (chunk.location.article, chunk.location.paragraph) == ("6", "3")
    )
    assert third.text.startswith("3. ")
    assert third.location.page == 2
    assert article_paragraphs(chunks, "7")[0] == "1"


def test_polish_text_keeps_its_diacritics(parser: DoclingDocumentParser) -> None:
    text = "\n".join(chunk.text for chunk in chunks_of(parser, "ai-act-art6-pl.pdf"))

    assert "o każdym wykorzystaniu" in text
    assert "Niniejszy artykuł nie ma wpływu" in text


@pytest.mark.parametrize(
    ("filename", "header"), [("ai-act-art6-en.pdf", "OJ L"), ("ai-act-art6-pl.pdf", "Dz.U. L")]
)
def test_page_headers_and_footers_are_dropped(
    parser: DoclingDocumentParser, filename: str, header: str
) -> None:
    assert not any(header in chunk.text for chunk in chunks_of(parser, filename))


def test_a_pdf_reports_its_page_count(parser: DoclingDocumentParser) -> None:
    content = (DOCUMENTS / "ai-act-art6-en.pdf").read_bytes()

    assert parser.parse("ai-act-art6-en.pdf", content).page_count == 2


def test_word_documents_keep_headings_and_tables(parser: DoclingDocumentParser) -> None:
    content = (DOCUMENTS / "retention-policy.docx").read_bytes()
    parsed = parser.parse("retention-policy.docx", content)
    chunks = chunk_document("doc", parsed)

    logs = next(chunk for chunk in chunks if "Logs are kept for six months" in chunk.text)
    assert logs.location.heading_path == ("Data retention policy", "Retention periods")
    [table] = [chunk for chunk in chunks if "Incident reports" in chunk.text]
    assert "5 years" in table.text
    assert table.location.heading_path == ("Data retention policy", "Retention periods")
    assert parsed.page_count is None


def test_a_numbered_list_in_a_word_document_stays_with_its_paragraph(
    parser: DoclingDocumentParser,
) -> None:
    chunks = chunks_of(parser, "retention-policy.docx")

    backups = next(chunk for chunk in chunks if "The team shall:" in chunk.text)
    assert "back up the logs every week;" in backups.text
    assert "test a restore every month." in backups.text


@pytest.mark.parametrize("filename", ["ai-act-art6-en-scan.pdf", "ai-act-art6-en-photo.jpg"])
def test_scans_and_photos_are_read_with_ocr(parser: DoclingDocumentParser, filename: str) -> None:
    chunks = chunks_of(parser, filename)

    first = next(chunk for chunk in chunks if chunk.location.article == "6")
    assert "Irrespective of whether an AI system" in first.text
    assert first.location.page == 1


def test_polish_photos_are_read_with_ocr(parser: DoclingDocumentParser) -> None:
    chunks = chunks_of(parser, "ai-act-art6-pl-photo.png")

    found = next(chunk for chunk in chunks if "Bez uszczerbku" in chunk.text)
    assert found.location.page == 1


def test_the_same_file_gives_the_same_chunks(parser: DoclingDocumentParser) -> None:
    assert chunks_of(parser, "ai-act-art6-en.pdf") == chunks_of(parser, "ai-act-art6-en.pdf")


@pytest.mark.parametrize(
    ("filename", "reason"),
    [
        ("locked.pdf", "password-protected"),
        ("corrupt.pdf", "not a readable PDF"),
        ("too-long.pdf", "at most 500 pages"),
    ],
)
def test_unreadable_files_raise_with_a_reason(
    parser: DoclingDocumentParser, filename: str, reason: str
) -> None:
    with pytest.raises(DocumentUnreadable, match=reason):
        parser.parse(filename, (DOCUMENTS / filename).read_bytes())


def test_a_pdf_without_text_has_no_blocks(parser: DoclingDocumentParser) -> None:
    assert parser.parse("blank.pdf", (DOCUMENTS / "blank.pdf").read_bytes()).blocks == ()


def test_missing_models_name_the_model_and_the_command(tmp_path: Path) -> None:
    with pytest.raises(ParserNotReady, match="make models") as raised:
        DoclingDocumentParser.ensure_ready(tmp_path)

    assert "docling-layout-heron" in str(raised.value)


def test_a_missing_ocr_engine_is_named(tmp_path: Path) -> None:
    with pytest.raises(ParserNotReady, match="tesseract"):
        DoclingDocumentParser.ensure_ready(MODELS_DIR, tesseract="tesseract-that-does-not-exist")
