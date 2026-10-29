import re

from harness.corpus import documents


def test_the_corpus_pins_the_ai_act_and_the_gdpr_in_english_and_polish() -> None:
    pinned = documents()

    assert {(document.celex, document.language) for document in pinned} == {
        ("32024R1689", "eng"),
        ("32024R1689", "pol"),
        ("32016R0679", "eng"),
        ("32016R0679", "pol"),
    }
    assert all(re.fullmatch(r"[0-9a-f]{64}", document.sha256) for document in pinned)
    assert len({document.file for document in pinned}) == len(pinned)
