import hashlib
import re
from pathlib import Path

import pytest

from assistant.adapters.docling_models import PINNED_MODELS, ParserNotReady, verify_models


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def models(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "layout").mkdir()
    (tmp_path / "layout" / "model.safetensors").write_bytes(b"weights")
    (tmp_path / "config.json").write_bytes(b"{}")
    return {"layout/model.safetensors": sha256(b"weights"), "config.json": sha256(b"{}")}


def test_models_matching_their_hashes_pass(tmp_path: Path, models: dict[str, str]) -> None:
    verify_models(tmp_path, models)


def test_a_missing_file_is_named_with_the_command_that_fetches_it(
    tmp_path: Path, models: dict[str, str]
) -> None:
    (tmp_path / "config.json").unlink()

    with pytest.raises(ParserNotReady, match=r"config\.json.*make models"):
        verify_models(tmp_path, models)


def test_a_file_with_other_content_is_rejected(tmp_path: Path, models: dict[str, str]) -> None:
    (tmp_path / "layout" / "model.safetensors").write_bytes(b"other weights")

    with pytest.raises(ParserNotReady, match=r"layout/model\.safetensors"):
        verify_models(tmp_path, models)


def test_every_model_is_pinned_to_a_commit_with_file_hashes() -> None:
    assert PINNED_MODELS.revisions
    for revision in PINNED_MODELS.revisions.values():
        assert re.fullmatch(r"[0-9a-f]{40}", revision)
    assert PINNED_MODELS.files
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in PINNED_MODELS.files.values())
