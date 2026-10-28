from assistant.domain.documents import document_id_for, split_into_chunks, title_from_filename


def test_blank_lines_separate_chunks() -> None:
    chunks = split_into_chunks("doc", "First paragraph.\n\nSecond paragraph.\nSame chunk.")

    assert [chunk.text for chunk in chunks] == [
        "First paragraph.",
        "Second paragraph.\nSame chunk.",
    ]


def test_whitespace_is_trimmed_and_empty_pieces_are_dropped() -> None:
    chunks = split_into_chunks("doc", "\n\n  One.  \n\n \n\n\nTwo.\n\n")

    assert [chunk.text for chunk in chunks] == ["One.", "Two."]


def test_chunks_carry_document_id_position_and_stable_id() -> None:
    chunks = split_into_chunks("abc", "One.\n\nTwo.")

    assert [(chunk.id, chunk.document_id, chunk.position) for chunk in chunks] == [
        ("abc:0", "abc", 0),
        ("abc:1", "abc", 1),
    ]


def test_same_content_gives_the_same_document_id() -> None:
    assert document_id_for("Some text.") == document_id_for("Some text.")


def test_different_content_gives_a_different_document_id() -> None:
    assert document_id_for("Some text.") != document_id_for("Other text.")


def test_document_id_is_sixteen_hex_characters() -> None:
    document_id = document_id_for("Some text.")

    assert len(document_id) == 16
    assert all(character in "0123456789abcdef" for character in document_id)


def test_title_is_the_filename_without_extension() -> None:
    assert title_from_filename("ai-act notes.md") == "ai-act notes"
