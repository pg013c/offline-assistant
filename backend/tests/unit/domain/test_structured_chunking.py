from assistant.domain.documents import (
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
