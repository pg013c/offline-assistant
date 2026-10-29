import hashlib
import re
from pathlib import Path

import pytest

from assistant.adapters.pinned_models import (
    BGE_M3,
    PINNED_MODELS,
    ModelsNotReady,
    PinnedModel,
    verify_models,
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def model(tmp_path: Path) -> PinnedModel:
    folder = tmp_path / "kind" / "org--model"
    (folder / "sub").mkdir(parents=True)
    (folder / "sub" / "weights.safetensors").write_bytes(b"weights")
    (folder / "config.json").write_bytes(b"{}")
    return PinnedModel(
        repository="org/model",
        revision="0" * 40,
        directory="kind/org--model",
        files={"sub/weights.safetensors": sha256(b"weights"), "config.json": sha256(b"{}")},
    )


def test_models_matching_their_hashes_pass(tmp_path: Path, model: PinnedModel) -> None:
    verify_models(tmp_path, [model])


def test_a_missing_file_names_the_model_and_the_command(tmp_path: Path, model: PinnedModel) -> None:
    (tmp_path / "kind" / "org--model" / "config.json").unlink()

    with pytest.raises(ModelsNotReady, match=r"org/model.*config\.json.*make models"):
        verify_models(tmp_path, [model])


def test_a_file_with_other_content_is_rejected(tmp_path: Path, model: PinnedModel) -> None:
    (tmp_path / "kind" / "org--model" / "sub" / "weights.safetensors").write_bytes(b"other")

    with pytest.raises(ModelsNotReady, match=r"sub/weights\.safetensors differs"):
        verify_models(tmp_path, [model])


def test_every_model_is_pinned_to_a_commit_with_file_hashes() -> None:
    assert {model.repository for model in PINNED_MODELS} >= {
        "docling-project/docling-layout-heron",
        "docling-project/docling-models",
        "BAAI/bge-m3",
    }
    for model in PINNED_MODELS:
        assert re.fullmatch(r"[0-9a-f]{40}", model.revision)
        assert model.files
        assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in model.files.values())


def test_bge_m3_keeps_the_dense_model_and_its_tokenizer_only() -> None:
    assert {"pytorch_model.bin", "tokenizer.json", "modules.json", "1_Pooling/config.json"} <= set(
        BGE_M3.files
    )
    assert not any(
        path.startswith(("onnx/", "imgs/")) or path in {"colbert_linear.pt", "sparse_linear.pt"}
        for path in BGE_M3.files
    )
