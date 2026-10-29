import hashlib
import json
import socket
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from harness.corpus import CorpusDocument, documents
from harness.run import (
    CorpusError,
    PortInUse,
    api_environment,
    default_config,
    drop_collections,
    ensure_port_free,
    verify_corpus,
    warm_up,
)


def pins(content: bytes) -> tuple[CorpusDocument, ...]:
    digest = hashlib.sha256(content).hexdigest()
    return tuple(replace(document, sha256=digest) for document in documents()[:2])


def test_a_verified_corpus_lists_its_files_with_their_hashes(tmp_path: Path) -> None:
    for document in documents()[:2]:
        (tmp_path / document.file).write_bytes(b"%PDF")

    verified = verify_corpus(tmp_path, pins(b"%PDF"))

    assert verified == {
        document.file: hashlib.sha256(b"%PDF").hexdigest() for document in documents()[:2]
    }


def test_a_missing_corpus_file_is_named_with_the_command_that_fetches_it(tmp_path: Path) -> None:
    (tmp_path / documents()[0].file).write_bytes(b"%PDF")

    with pytest.raises(CorpusError, match=rf"{documents()[1].file}.*make eval-corpus"):
        verify_corpus(tmp_path, pins(b"%PDF"))


def test_a_changed_corpus_file_is_refused(tmp_path: Path) -> None:
    for document in documents()[:2]:
        (tmp_path / document.file).write_bytes(b"%PDF edited")

    with pytest.raises(CorpusError, match="differs from the pinned"):
        verify_corpus(tmp_path, pins(b"%PDF"))


def test_a_port_already_in_use_is_refused() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        with pytest.raises(PortInUse, match=str(port)):
            ensure_port_free(port)


def test_only_the_runs_own_collections_are_dropped() -> None:
    deleted: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            deleted.append(request.url.path)
            return httpx.Response(200, json={"result": True})
        names = ["eval-baai-bge-m3-v1", "assistant-baai-bge-m3-v1", "evaluation-x", "e2e-x"]
        return httpx.Response(
            200, json={"result": {"collections": [{"name": name} for name in names]}}
        )

    with httpx.Client(transport=httpx.MockTransport(handle), base_url="http://qdrant") as qdrant:
        drop_collections(qdrant, prefix="eval")

    assert deleted == ["/collections/eval-baai-bge-m3-v1"]


def test_the_evaluation_settings_do_not_come_from_the_development_environment() -> None:
    config = default_config(
        {
            "ASSISTANT_MIN_SIMILARITY": "0.9",
            "ASSISTANT_QDRANT_URL": "http://elsewhere:6333",
            "QDRANT_PORT": "6340",
        }
    )

    assert config.threshold == 0.5
    assert config.qdrant_url == "http://127.0.0.1:6340"
    assert config.collection_prefix == "eval"


def test_the_evaluation_api_runs_with_the_reranker_whatever_the_environment_says() -> None:
    config = default_config({})

    env = api_environment(config, {"PATH": "/usr/bin", "ASSISTANT_RERANKER": "off"})

    assert env["ASSISTANT_RERANKER"] == "on"
    assert env["PATH"] == "/usr/bin"


def test_a_warm_up_search_asks_for_its_mode_and_returns_its_time() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api") as api:
        elapsed = warm_up(api, "hybrid")

    assert bodies == [{"query": "warm-up", "limit": 10, "rerank": False}]
    assert elapsed >= 0
