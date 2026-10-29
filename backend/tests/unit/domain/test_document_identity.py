from assistant.domain.documents import document_id_for, title_from_filename


def test_same_content_gives_the_same_document_id() -> None:
    assert document_id_for(b"Some text.") == document_id_for(b"Some text.")


def test_different_content_gives_a_different_document_id() -> None:
    assert document_id_for(b"Some text.") != document_id_for(b"Other text.")


def test_document_id_is_sixteen_hex_characters() -> None:
    document_id = document_id_for(b"Some text.")

    assert len(document_id) == 16
    assert all(character in "0123456789abcdef" for character in document_id)


def test_title_is_the_filename_without_extension() -> None:
    assert title_from_filename("ai-act notes.md") == "ai-act notes"
