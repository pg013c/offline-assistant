import pytest

from assistant.domain.documents import (
    CHUNKER_VERSION,
    Block,
    ChunkLocation,
    ParsedDocument,
    chunk_document,
)


def heading(text: str, level: int = 1, page: int | None = 1) -> Block:
    return Block(kind="heading", text=text, page=page, level=level)


def paragraph(text: str, page: int | None = 1) -> Block:
    return Block(kind="paragraph", text=text, page=page)


def list_item(text: str, page: int | None = 1) -> Block:
    return Block(kind="list_item", text=text, page=page)


def table(text: str, page: int | None = 1) -> Block:
    return Block(kind="table", text=text, page=page)


def parsed(*blocks: Block, page_count: int = 1) -> ParsedDocument:
    return ParsedDocument(page_count=page_count, blocks=tuple(blocks))


def test_each_paragraph_under_a_heading_is_a_chunk_with_its_heading_and_page() -> None:
    document = parsed(
        heading("Scope"),
        paragraph("First paragraph.", page=1),
        paragraph("Second paragraph.", page=2),
        page_count=2,
    )

    chunks = chunk_document("doc", document)

    assert [(chunk.text, chunk.location) for chunk in chunks] == [
        ("First paragraph.", ChunkLocation(heading_path=("Scope",), page=1)),
        ("Second paragraph.", ChunkLocation(heading_path=("Scope",), page=2)),
    ]


def test_headings_nest_by_level_and_a_new_heading_replaces_its_siblings() -> None:
    document = parsed(
        heading("Chapter I", level=1),
        heading("Section 1", level=2),
        paragraph("In section one."),
        heading("Section 2", level=2),
        paragraph("In section two."),
        heading("Chapter II", level=1),
        paragraph("In chapter two."),
    )

    chunks = chunk_document("doc", document)

    assert [chunk.location.heading_path for chunk in chunks] == [
        ("Chapter I", "Section 1"),
        ("Chapter I", "Section 2"),
        ("Chapter II",),
    ]


def test_headings_are_not_chunks_of_their_own() -> None:
    document = parsed(heading("Title"), heading("Empty section", level=2))

    assert chunk_document("doc", document) == []


def test_list_items_join_the_paragraph_they_follow() -> None:
    document = parsed(
        heading("Duties"),
        paragraph("Providers shall:"),
        list_item("(a) keep logs;"),
        list_item("(b) report incidents."),
        paragraph("Next paragraph."),
    )

    chunks = chunk_document("doc", document)

    assert [chunk.text for chunk in chunks] == [
        "Providers shall:\n(a) keep logs;\n(b) report incidents.",
        "Next paragraph.",
    ]


def test_a_long_paragraph_is_split_at_sentence_boundaries_within_the_limit() -> None:
    sentences = [f"Sentence number {n} has a few words." for n in range(20)]
    document = parsed(heading("Long"), paragraph(" ".join(sentences)))

    chunks = chunk_document("doc", document, max_chars=120)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 120 for chunk in chunks)
    assert all(chunk.text.endswith(".") for chunk in chunks)
    assert " ".join(chunk.text for chunk in chunks) == " ".join(sentences)
    assert {chunk.location.heading_path for chunk in chunks} == {("Long",)}


def test_a_sentence_longer_than_the_limit_is_split_between_words() -> None:
    words = " ".join(f"word{n}" for n in range(100))
    document = parsed(paragraph(words + "."))

    chunks = chunk_document("doc", document, max_chars=80)

    assert all(len(chunk.text) <= 80 for chunk in chunks)
    assert " ".join(chunk.text for chunk in chunks) == words + "."


def test_a_table_is_one_chunk_however_long() -> None:
    rows = "\n".join(f"| row {n} | value {n} |" for n in range(50))
    document = parsed(heading("Annex"), table(rows))

    chunks = chunk_document("doc", document, max_chars=100)

    assert [chunk.text for chunk in chunks] == [rows]
    assert chunks[0].location == ChunkLocation(heading_path=("Annex",), page=1)


def test_chunks_get_positional_ids_and_the_same_input_gives_the_same_chunks() -> None:
    document = parsed(heading("H"), paragraph("One."), paragraph("Two."))

    first = chunk_document("abc", document)
    second = chunk_document("abc", document)

    assert [(chunk.id, chunk.document_id, chunk.position) for chunk in first] == [
        ("abc:0", "abc", 0),
        ("abc:1", "abc", 1),
    ]
    assert first == second


def test_blank_blocks_are_dropped() -> None:
    document = parsed(paragraph("  "), paragraph(" Text. "))

    assert [chunk.text for chunk in chunk_document("doc", document)] == ["Text."]


def article_6(word: str = "Article") -> ParsedDocument:
    return parsed(
        heading("CHAPTER III", level=1, page=52),
        heading(f"{word} 6", level=2, page=53),
        heading("Classification rules for high-risk AI systems", level=2, page=53),
        paragraph("1. An AI system shall be considered high-risk where:", page=53),
        list_item("(a) it is a safety component;", page=53),
        paragraph("(b) it requires a conformity assessment.", page=54),
        paragraph("2. AI systems referred to in Annex III shall be considered high-risk.", page=54),
        paragraph("The first subparagraph shall not apply where the risk is low.", page=54),
        page_count=60,
    )


def test_numbered_paragraphs_of_an_article_are_chunks_labelled_with_article_and_paragraph() -> None:
    chunks = chunk_document("doc", article_6())

    assert [
        (chunk.location.article, chunk.location.paragraph, chunk.location.page) for chunk in chunks
    ] == [("6", "1", 53), ("6", "2", 54)]
    assert chunks[0].text == (
        "1. An AI system shall be considered high-risk where:\n"
        "(a) it is a safety component;\n"
        "(b) it requires a conformity assessment."
    )
    assert chunks[1].text.endswith("shall not apply where the risk is low.")
    assert chunks[0].location.heading_path == (
        "CHAPTER III",
        "Article 6",
        "Classification rules for high-risk AI systems",
    )


def test_polish_articles_are_recognised() -> None:
    chunks = chunk_document("doc", article_6("Artykuł"))

    assert [(chunk.location.article, chunk.location.paragraph) for chunk in chunks] == [
        ("6", "1"),
        ("6", "2"),
    ]


def test_an_article_number_in_a_paragraph_starts_the_article() -> None:
    document = parsed(
        paragraph("Art. 12"),
        paragraph("1. Records shall be kept."),
        paragraph("Article 13a"),
        paragraph("1. Transparency is required."),
    )

    chunks = chunk_document("doc", document)

    assert [(chunk.location.article, chunk.location.paragraph, chunk.text) for chunk in chunks] == [
        ("12", "1", "1. Records shall be kept."),
        ("13a", "1", "1. Transparency is required."),
    ]


def test_an_article_without_numbered_paragraphs_is_one_chunk() -> None:
    document = parsed(
        heading("Article 3"),
        paragraph("This Regulation applies to providers."),
        paragraph("It also applies to deployers."),
    )

    chunks = chunk_document("doc", document)

    assert [(chunk.location.article, chunk.location.paragraph, chunk.text) for chunk in chunks] == [
        ("3", None, "This Regulation applies to providers.\nIt also applies to deployers."),
    ]


def test_no_chunk_holds_text_from_two_articles() -> None:
    document = parsed(
        heading("Article 1"),
        paragraph("Short subject matter."),
        heading("Article 2"),
        paragraph("Short scope."),
        heading("SECTION 2", level=1),
        paragraph("Text after the articles."),
    )

    chunks = chunk_document("doc", document)

    assert [(chunk.location.article, chunk.text) for chunk in chunks] == [
        ("1", "Short subject matter."),
        ("2", "Short scope."),
        (None, "Text after the articles."),
    ]
    assert chunks[2].location.heading_path == ("SECTION 2",)


def test_a_long_numbered_paragraph_is_split_and_keeps_its_labels() -> None:
    sentences = " ".join(f"Obligation {n} applies to providers." for n in range(30))
    document = parsed(heading("Article 16"), paragraph(f"1. {sentences}"))

    chunks = chunk_document("doc", document, max_chars=200)

    assert len(chunks) > 1
    assert {(chunk.location.article, chunk.location.paragraph) for chunk in chunks} == {("16", "1")}


def test_a_numbered_list_outside_an_article_joins_its_paragraph() -> None:
    document = parsed(
        heading("Backups"),
        paragraph("The team shall:"),
        list_item("1. back up weekly;"),
        list_item("2. test a restore every month."),
    )

    chunks = chunk_document("doc", document)

    assert [chunk.text for chunk in chunks] == [
        "The team shall:\n1. back up weekly;\n2. test a restore every month."
    ]


def test_numbered_list_items_inside_an_article_are_its_paragraphs() -> None:
    document = parsed(
        heading("Article 6"),
        list_item("1. An AI system is high-risk where:"),
        list_item("(a) it is a safety component."),
        list_item("2. Annex III systems are high-risk."),
    )

    chunks = chunk_document("doc", document)

    assert [(chunk.location.paragraph, chunk.text) for chunk in chunks] == [
        ("1", "1. An AI system is high-risk where:\n(a) it is a safety component."),
        ("2", "2. Annex III systems are high-risk."),
    ]


def test_a_word_longer_than_the_limit_is_cut_to_fit() -> None:
    word = "x" * 250
    document = parsed(paragraph(f"See {word} here."))

    chunks = chunk_document("doc", document, max_chars=100)

    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks).replace(" ", "") == f"See{word}here."


def test_each_part_of_a_split_chunk_gets_the_page_it_starts_on() -> None:
    first = " ".join(f"Page one sentence {n}." for n in range(6))
    second = " ".join(f"Page two sentence {n}." for n in range(6))
    document = parsed(
        heading("Article 9", page=1),
        paragraph(f"1. {first}", page=1),
        paragraph(second, page=2),
        page_count=2,
    )

    chunks = chunk_document("doc", document, max_chars=120)

    pages = [(chunk.text.split()[0:2], chunk.location.page) for chunk in chunks]
    assert chunks[0].location.page == 1
    assert chunks[-1].location.page == 2
    for words, page in pages:
        if words == ["Page", "two"]:
            assert page == 2
        if words == ["Page", "one"]:
            assert page == 1


def test_a_title_right_after_a_heading_joins_the_heading_path() -> None:
    document = parsed(
        heading("SEKCJA 3"),
        paragraph("Obowiązki dostawców i podmiotów stosujących systemy AI wysokiego ryzyka"),
        paragraph("Dostawcy zapewniają zgodność systemów z wymogami."),
    )

    chunks = chunk_document("doc", document)

    assert [chunk.text for chunk in chunks] == ["Dostawcy zapewniają zgodność systemów z wymogami."]
    assert chunks[0].location.heading_path == (
        "SEKCJA 3",
        "Obowiązki dostawców i podmiotów stosujących systemy AI wysokiego ryzyka",
    )


@pytest.mark.parametrize(
    "line",
    [
        "This Regulation applies to providers.",
        "Providers shall:",
        "Having regard to the Treaty on the Functioning of the European Union,",
        "x" * 201,
    ],
)
def test_a_paragraph_that_does_not_look_like_a_title_stays_a_chunk(line: str) -> None:
    document = parsed(heading("Scope"), paragraph(line))

    assert [chunk.text for chunk in chunk_document("doc", document)] == [line]


def test_a_title_like_line_after_other_content_stays_a_chunk() -> None:
    document = parsed(
        heading("Scope"),
        paragraph("This Regulation applies to providers."),
        paragraph("Annex overview"),
    )

    assert [chunk.text for chunk in chunk_document("doc", document)] == [
        "This Regulation applies to providers.",
        "Annex overview",
    ]


def test_the_chunker_version_is_raised_with_the_new_rule() -> None:
    assert CHUNKER_VERSION == 2
