from pathlib import Path

import pytest

from assistant.adapters.bge_reranker import BgeReranker
from assistant.adapters.pinned_models import ModelsNotReady


def test_missing_files_name_the_reranker_and_make_models(tmp_path: Path) -> None:
    with pytest.raises(ModelsNotReady, match=r"BAAI/bge-reranker-v2-m3.*make models"):
        BgeReranker.ensure_ready(tmp_path)


def test_the_model_id_names_the_pinned_revision(tmp_path: Path) -> None:
    assert BgeReranker(tmp_path).model_id == "BAAI/bge-reranker-v2-m3@953dc6f6"


def test_no_passages_need_no_model(tmp_path: Path) -> None:
    # Nothing is loaded from the empty directory when there is nothing to score.
    assert BgeReranker(tmp_path).score("query", []) == []
