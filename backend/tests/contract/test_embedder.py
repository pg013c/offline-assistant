"""Contract for the Embedder port; the real adapter runs it in tests/integration."""

import math
import os
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from assistant.adapters.fakes.embedder import FakeEmbedder
from assistant.ports.embedder import Embedder

MODELS_DIR = Path(
    os.environ.get("ASSISTANT_MODELS_DIR", Path(__file__).parents[3] / "data" / "models")
)


def bge_m3() -> Embedder:
    # Imported here: loading sentence-transformers is slow and only integration runs need it.
    from assistant.adapters.sentence_transformer_embedder import (  # noqa: PLC0415
        SentenceTransformerEmbedder,
    )

    SentenceTransformerEmbedder.ensure_ready(MODELS_DIR)
    return SentenceTransformerEmbedder(MODELS_DIR)


ADAPTERS = [
    pytest.param(FakeEmbedder, id="fake"),
    pytest.param(bge_m3, id="bge-m3", marks=pytest.mark.integration),
]

RELATED = ("Providers keep logs for six months.", "Providers must keep their logs.")
UNRELATED = "Bake the bread for forty minutes."


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@pytest.mark.parametrize("factory", ADAPTERS)
def test_embedder_contract(factory: Callable[[], Embedder]) -> None:
    embedder = factory()

    vectors = embedder.embed([*RELATED, UNRELATED])
    query = embedder.embed_query(RELATED[0])

    assert embedder.model_id
    assert len(vectors) == 3
    assert all(len(vector) == embedder.dimensions for vector in [*vectors, query])
    assert all(math.isclose(math.hypot(*vector), 1.0, abs_tol=1e-3) for vector in vectors)
    assert embedder.embed([RELATED[0]]) == embedder.embed([RELATED[0]])
    assert cosine(vectors[0], vectors[1]) > cosine(vectors[0], vectors[2])
    assert cosine(query, vectors[1]) > cosine(query, vectors[2])


def test_the_fake_relates_the_polish_and_english_words_of_its_table() -> None:
    embedder = FakeEmbedder()
    english, polish, unrelated = embedder.embed(
        ["When is an AI system high-risk?", "Kiedy system AI jest wysokiego ryzyka?", UNRELATED]
    )

    assert cosine(english, polish) > cosine(english, unrelated)
