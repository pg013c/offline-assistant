import pytest

from harness.dataset import Case, ExpectedSource
from harness.resolve import ChunkRef, UnresolvedSource, resolve

CHUNKS = [
    ChunkRef("en:1", "ai-act-en", "6", "1", ("Article 6",)),
    ChunkRef("en:2", "ai-act-en", "6", "2", ("Article 6",)),
    ChunkRef(
        "en:3", "ai-act-en", None, None, ("High-risk AI systems referred to in Article 6(2)",)
    ),
    ChunkRef("pl:1", "ai-act-pl", "6", "1", ("Artykuł 6",)),
]


def case(case_id: str, *sources: ExpectedSource, behaviour: str = "answer") -> Case:
    return Case(case_id, "single-article", "en", "?", behaviour, tuple(sources))


def test_a_source_resolves_to_the_chunks_of_its_document_and_location() -> None:
    resolved = resolve([case("a", ExpectedSource("ai-act-en", "6", "2"))], CHUNKS)

    assert resolved == {"a": frozenset({"en:2"})}


def test_a_source_without_a_paragraph_matches_every_paragraph_of_the_article() -> None:
    resolved = resolve([case("a", ExpectedSource("ai-act-en", "6"))], CHUNKS)

    assert resolved == {"a": frozenset({"en:1", "en:2"})}


def test_a_heading_source_matches_chunks_under_that_heading() -> None:
    source = ExpectedSource("ai-act-en", heading="High-risk AI systems referred to in Article 6(2)")

    assert resolve([case("a", source)], CHUNKS) == {"a": frozenset({"en:3"})}


def test_several_sources_resolve_to_all_their_chunks() -> None:
    sources = (ExpectedSource("ai-act-en", "6", "1"), ExpectedSource("ai-act-pl", "6", "1"))

    assert resolve([case("a", *sources)], CHUNKS) == {"a": frozenset({"en:1", "pl:1"})}


def test_an_out_of_scope_case_resolves_to_nothing() -> None:
    assert resolve([case("oos", behaviour="refuse")], CHUNKS) == {"oos": frozenset()}


def test_an_unresolved_source_names_the_case_and_the_source() -> None:
    with pytest.raises(UnresolvedSource, match=r"broken.*gdpr-en.*Art\. 99"):
        resolve([case("broken", ExpectedSource("gdpr-en", "99"))], CHUNKS)
