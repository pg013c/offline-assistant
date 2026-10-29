"""BGE-M3 through sentence-transformers (ADR 0017). Needs `make models`."""

import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from assistant.adapters.pinned_models import ModelsNotReady
from assistant.adapters.sentence_transformer_embedder import SentenceTransformerEmbedder

pytestmark = pytest.mark.integration

MODELS_DIR = Path(
    os.environ.get("ASSISTANT_MODELS_DIR", Path(__file__).parents[3] / "data" / "models")
)


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformerEmbedder:
    SentenceTransformerEmbedder.ensure_ready(MODELS_DIR)
    return SentenceTransformerEmbedder(MODELS_DIR)


def test_bge_m3_has_1024_dimensions_and_names_its_pinned_version(
    embedder: SentenceTransformerEmbedder,
) -> None:
    assert embedder.dimensions == 1024
    assert embedder.model_id.startswith("BAAI/bge-m3@")


def test_a_polish_and_an_english_question_about_the_same_thing_are_close(
    embedder: SentenceTransformerEmbedder,
) -> None:
    polish, english, cooking = embedder.embed(
        [
            "Kiedy system sztucznej inteligencji uznaje się za system wysokiego ryzyka?",
            "When is an AI system considered high-risk?",
            "How long should pasta boil?",
        ]
    )

    assert cosine(polish, english) > cosine(polish, cooking) + 0.2


def test_missing_weights_name_the_model_and_make_models(tmp_path: Path) -> None:
    with pytest.raises(ModelsNotReady, match=r"BAAI/bge-m3.*make models"):
        SentenceTransformerEmbedder.ensure_ready(tmp_path)
