"""Retrieval on the AI Act excerpts with BGE-M3 and Qdrant (F-03 AC-2 to AC-4).

These fixed cases become evaluation cases in F-04. Needs `make models` and `make qdrant`.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from assistant.adapters.docling_parser import DoclingDocumentParser
from assistant.adapters.qdrant_chunk_index import QdrantChunkIndex
from assistant.adapters.sentence_transformer_embedder import SentenceTransformerEmbedder
from assistant.domain.documents import chunk_document, document_id_for
from assistant.settings import Settings

pytestmark = pytest.mark.integration

DOCUMENTS = Path(__file__).parents[1] / "fixtures" / "documents"
MODELS_DIR = Path(
    os.environ.get("ASSISTANT_MODELS_DIR", Path(__file__).parents[3] / "data" / "models")
)
QDRANT_URL = os.environ.get("ASSISTANT_QDRANT_URL", "http://127.0.0.1:6333")
# The threshold the app uses by default.
MIN_SIMILARITY = Settings.model_fields["min_similarity"].default


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder(MODELS_DIR)


def indexed(language: str, embedder: SentenceTransformerEmbedder) -> Iterator[QdrantChunkIndex]:
    """One excerpt, alone in a collection of its own."""
    content = (DOCUMENTS / f"ai-act-art6-{language}.pdf").read_bytes()
    parsed = DoclingDocumentParser(MODELS_DIR).parse(f"ai-act-art6-{language}.pdf", content)
    index = QdrantChunkIndex.connect(
        QDRANT_URL, embedder, prefix=f"test-{language}-{uuid.uuid4().hex[:8]}"
    )
    index.add(chunk_document(document_id_for(content), parsed))
    yield index
    index.drop()


@pytest.fixture(scope="module")
def english(embedder: SentenceTransformerEmbedder) -> Iterator[QdrantChunkIndex]:
    yield from indexed("en", embedder)


@pytest.fixture(scope="module")
def polish(embedder: SentenceTransformerEmbedder) -> Iterator[QdrantChunkIndex]:
    yield from indexed("pl", embedder)


def test_a_polish_question_finds_article_6_of_the_english_text(english: QdrantChunkIndex) -> None:
    results = english.search(
        "Kiedy system AI przeznaczony do użycia jako element bezpieczeństwa produktu "
        "uznaje się za system wysokiego ryzyka?",
        limit=3,
    )

    assert ("6", "1") in [(r.chunk.location.article, r.chunk.location.paragraph) for r in results]
    assert results[0].similarity >= MIN_SIMILARITY


def test_an_english_question_finds_article_6_of_the_polish_text(polish: QdrantChunkIndex) -> None:
    results = polish.search(
        "When is an AI system that is a safety component of a product considered high-risk?",
        limit=3,
    )

    assert ("6", "1") in [(r.chunk.location.article, r.chunk.location.paragraph) for r in results]
    assert results[0].similarity >= MIN_SIMILARITY


def test_an_exact_term_ranks_a_chunk_containing_it_first(english: QdrantChunkIndex) -> None:
    first, *others = english.search("Which AI systems does Annex III refer to?", limit=3)

    assert "Annex III" in first.chunk.text
    # It wins through the keyword half: another chunk is closer in meaning (AC-3).
    assert any(other.similarity > first.similarity for other in others)


@pytest.mark.parametrize("question", ["How long should pasta boil?", "Jak długo gotować makaron?"])
def test_an_unrelated_question_stays_below_the_threshold(
    english: QdrantChunkIndex, polish: QdrantChunkIndex, question: str
) -> None:
    for index in (english, polish):
        assert all(r.similarity < MIN_SIMILARITY for r in index.search(question, limit=3))
