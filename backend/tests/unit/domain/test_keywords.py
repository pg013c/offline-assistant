import pytest

from assistant.domain.keywords import BM25_K1, bm25_terms, token_id, tokens


def test_tokens_are_lower_cased_words_and_numbers_in_any_script() -> None:
    assert tokens("Artykuł 6 ust. 2: Annex III, high-risk AI.") == [
        "artykuł",
        "6",
        "ust",
        "2",
        "annex",
        "iii",
        "high",
        "risk",
        "ai",
    ]


def test_token_ids_are_stable_across_processes() -> None:
    # SHA-256 based, so the same word gets the same id in every run and on every machine.
    assert token_id("article") == 70859485
    assert token_id("artykuł") == 1548387116


def test_token_ids_fit_in_31_bits() -> None:
    assert all(0 <= token_id(word) < 2**31 for word in ["a", "zażółć", "123456789"])


def test_a_term_once_weighs_one() -> None:
    assert bm25_terms("annex") == {token_id("annex"): pytest.approx(1.0)}


def test_repeated_terms_saturate() -> None:
    weights = bm25_terms("logs logs logs logs")

    weight = weights[token_id("logs")]
    assert 1.0 < weight < BM25_K1 + 1
    assert weight == pytest.approx(4 * (BM25_K1 + 1) / (4 + BM25_K1))


def test_empty_text_has_no_terms() -> None:
    assert bm25_terms("  ,.;  ") == {}
