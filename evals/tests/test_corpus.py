import hashlib
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from harness.corpus import EVALS_DIR, documents, fetch


def test_the_corpus_pins_the_ai_act_and_the_gdpr_in_english_and_polish() -> None:
    pinned = documents()

    assert {
        (document.celex, document.language) for document in pinned if document.path is None
    } == {
        ("32024R1689", "eng"),
        ("32024R1689", "pol"),
        ("32016R0679", "eng"),
        ("32016R0679", "pol"),
    }
    assert all(re.fullmatch(r"[0-9a-f]{64}", document.sha256) for document in pinned)
    assert len({document.file for document in pinned}) == len(pinned)


def serving(content: bytes, requests: list[str]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, content=content)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_only_missing_files_are_downloaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = documents()[:2]
    monkeypatch.setattr("harness.corpus.documents", lambda: pinned)
    content = b"%PDF pinned"
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(
        "harness.corpus.documents",
        lambda: [replace(document, sha256=digest) for document in pinned],
    )
    (tmp_path / pinned[0].file).write_bytes(content)
    requests: list[str] = []

    fetch(tmp_path, client=serving(content, requests))

    assert len(requests) == 1
    assert (tmp_path / pinned[1].file).read_bytes() == content


def test_a_download_with_another_hash_stops_and_is_not_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("harness.corpus.documents", lambda: documents()[:1])

    with pytest.raises(SystemExit, match="differs from the pinned"):
        fetch(tmp_path, client=serving(b"something else", []))

    assert not any(tmp_path.iterdir())


def test_the_injected_documents_are_local_and_only_for_the_answer_suite() -> None:
    local = [document for document in documents() if document.path is not None]

    assert {document.file for document in local} == {
        "injected-retention-policy.md",
        "injected-model-card.md",
        "injected-note-request.md",
    }
    for document in local:
        assert document.answers_only
        assert document.celex is None
        assert hashlib.sha256((EVALS_DIR / str(document.path)).read_bytes()).hexdigest() == (
            document.sha256
        )


def test_a_local_document_is_copied_from_the_repository_and_never_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = [document for document in documents() if document.path is not None]
    monkeypatch.setattr("harness.corpus.documents", lambda: local)
    requests: list[str] = []

    fetch(tmp_path, client=serving(b"never served", requests))

    assert requests == []
    for document in local:
        assert (tmp_path / document.file).read_bytes() == (
            EVALS_DIR / str(document.path)
        ).read_bytes()


def test_a_local_document_that_differs_from_its_pin_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = next(document for document in documents() if document.path is not None)
    monkeypatch.setattr("harness.corpus.documents", lambda: [replace(local, sha256="0" * 64)])

    with pytest.raises(SystemExit, match="differs from the pinned"):
        fetch(tmp_path, client=serving(b"", []))

    assert not any(tmp_path.iterdir())
