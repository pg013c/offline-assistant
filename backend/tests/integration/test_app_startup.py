"""The app built from the environment with real adapters. Needs `make models` and `make qdrant`."""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from assistant.adapters.pinned_models import ModelsNotReady
from assistant.adapters.qdrant_chunk_index import IndexNotReady
from assistant.app import main

pytestmark = pytest.mark.integration

MODELS_DIR = Path(
    os.environ.get("ASSISTANT_MODELS_DIR", Path(__file__).parents[3] / "data" / "models")
)
QDRANT_URL = os.environ.get("ASSISTANT_QDRANT_URL", "http://127.0.0.1:6333")


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    prefix = f"test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(MODELS_DIR))
    monkeypatch.setenv("ASSISTANT_QDRANT_URL", QDRANT_URL)
    monkeypatch.setenv("ASSISTANT_QDRANT_COLLECTION_PREFIX", prefix)
    # The test model: these tests are about startup, not a running LLM server (F-06).
    monkeypatch.setenv("ASSISTANT_CHAT_MODEL", "fake-extractive")
    # main() sets these; recording them here restores them after the test.
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    yield prefix
    client = QdrantClient(url=QDRANT_URL)
    for collection in client.get_collections().collections:
        if collection.name.startswith(prefix):
            client.delete_collection(collection.name)


def test_the_app_builds_from_the_environment_with_real_adapters(environment: str) -> None:
    app = main()

    assert app.state.settings.qdrant_collection_prefix == environment
    collections = [item.name for item in QdrantClient(url=QDRANT_URL).get_collections().collections]
    assert any(name.startswith(f"{environment}-baai-bge-m3") for name in collections)


def test_an_unreachable_qdrant_stops_the_app_with_the_variable_and_command(
    environment: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASSISTANT_QDRANT_URL", "http://127.0.0.1:9")

    with pytest.raises(IndexNotReady, match=r"ASSISTANT_QDRANT_URL.*make qdrant"):
        main()


def test_a_missing_reranker_stops_the_app_naming_it(
    environment: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Every model but the reranker.
    models = tmp_path / "models"
    models.mkdir()
    for kind in ("docling", "embeddings"):
        (models / kind).symlink_to(MODELS_DIR / kind)
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(models))
    # Explicitly on: the automatic default leaves the reranker off on a CPU, as in CI.
    monkeypatch.setenv("ASSISTANT_RERANKER", "on")

    with pytest.raises(ModelsNotReady, match=r"BAAI/bge-reranker-v2-m3.*make models"):
        main()


def test_with_reranking_off_the_app_starts_without_the_reranker(
    environment: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    models = tmp_path / "models"
    models.mkdir()
    for kind in ("docling", "embeddings"):
        (models / kind).symlink_to(MODELS_DIR / kind)
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(models))
    monkeypatch.setenv("ASSISTANT_RERANKER", "off")

    assert main().state.settings.reranker == "off"
