from assistant.domain.documents import Chunk, ChunkLocation, indexed_text


def chunk(heading_path: tuple[str, ...], text: str = "1. Providers shall ensure...") -> Chunk:
    return Chunk(
        id="doc:0",
        document_id="doc",
        position=0,
        text=text,
        location=ChunkLocation(heading_path=heading_path, article="50", paragraph="1"),
    )


def test_the_heading_path_comes_before_the_text() -> None:
    passage = chunk(("CHAPTER IV", "Article 50", "Transparency obligations"))

    assert indexed_text(passage) == (
        "CHAPTER IV > Article 50 > Transparency obligations\n\n1. Providers shall ensure..."
    )


def test_a_chunk_without_headings_is_indexed_as_its_text() -> None:
    assert indexed_text(chunk(())) == "1. Providers shall ensure..."


def test_the_chunk_keeps_its_own_text() -> None:
    passage = chunk(("Article 50",))

    indexed_text(passage)

    assert passage.text == "1. Providers shall ensure..."
