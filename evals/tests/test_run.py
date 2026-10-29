"""The whole harness on the F-02 excerpts. Needs `make models` and `make qdrant`."""

import hashlib
import json
import os
import shutil
import socket
import uuid
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from harness.corpus import documents
from harness.run import GATED_MODE, RunConfig, run

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
EXCERPTS = ROOT / "backend" / "tests" / "fixtures" / "documents"
QDRANT_URL = os.environ.get("ASSISTANT_QDRANT_URL", "http://127.0.0.1:6333")
PORT = 8029


def collections() -> list[str]:
    response = httpx.get(f"{QDRANT_URL}/collections")
    return [item["name"] for item in response.json()["result"]["collections"]]


@pytest.fixture
def config(tmp_path: Path) -> Iterator[RunConfig]:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    # The excerpts stand in for the full regulation under its corpus name.
    shutil.copy(EXCERPTS / "ai-act-art6-en.pdf", corpus / "ai-act-en.pdf")
    shutil.copy(EXCERPTS / "ai-act-art6-pl.pdf", corpus / "ai-act-pl.pdf")
    prefix = f"evaltest-{uuid.uuid4().hex[:8]}"
    # Pinned like the real corpus, with the excerpts' own hashes.
    pins = tuple(
        replace(document, sha256=hashlib.sha256((corpus / document.file).read_bytes()).hexdigest())
        for document in documents()
        if (corpus / document.file).exists()
    )
    yield RunConfig(
        corpus=pins,
        corpus_dir=corpus,
        dataset=Path(__file__).parent / "fixtures" / "excerpts.yaml",
        baseline=tmp_path / "baseline.json",
        results_dir=tmp_path / "results",
        data_dir=tmp_path / "data",
        models_dir=Path(os.environ.get("ASSISTANT_MODELS_DIR", ROOT / "data" / "models")),
        qdrant_url=QDRANT_URL,
        collection_prefix=prefix,
        port=PORT,
        threshold=0.5,
    )
    for name in collections():
        if name.startswith(prefix):
            httpx.delete(f"{QDRANT_URL}/collections/{name}")


def test_every_run_starts_from_an_empty_index_and_records_its_inputs(config: RunConfig) -> None:
    run(config)

    second = run(config)

    report = json.loads(second.report_json.read_text(encoding="utf-8"))
    metadata = report["metadata"]
    assert metadata["indexing_seconds"] > 0
    assert set(metadata["corpus"]) == {"ai-act-en.pdf", "ai-act-pl.pdf"}
    assert report["expected"]["fixture-en-article-6"]


def test_a_run_indexes_the_corpus_scores_the_cases_and_writes_a_report(config: RunConfig) -> None:
    others_before = [
        name for name in collections() if not name.startswith(config.collection_prefix)
    ]

    outcome = run(config)

    report = json.loads(outcome.report_json.read_text(encoding="utf-8"))
    assert set(report["metrics"]) == {
        "recall@3",
        "recall@10",
        "mrr",
        "out_of_scope_refused",
        "in_scope_unanswered",
    }
    assert report["metrics"]["recall@3"]["cases"] == 2
    assert report["metrics"]["out_of_scope_refused"]["cases"] == 1
    assert outcome.report_markdown.read_text(encoding="utf-8").startswith("| Metric |")
    assert report["gated_mode"] == GATED_MODE == "reranked"
    assert set(report["modes"]) == {"reranked", "hybrid"}
    for mode in report["modes"].values():
        assert mode["metrics"]["recall@3"]["cases"] == 2
        assert mode["latency_ms"]["median"] > 0
        assert mode["out_of_scope_top_similarity"] is not None
    assert outcome.gate_failures == []
    # The API it started is gone, and no other collection was touched.
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", PORT)) != 0
    assert [n for n in collections() if not n.startswith(config.collection_prefix)] == others_before
