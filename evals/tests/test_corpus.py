import hashlib
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from harness.corpus import documents, fetch


def test_the_corpus_pins_the_ai_act_and_the_gdpr_in_english_and_polish() -> None:
    pinned = documents()

    assert {(document.celex, document.language) for document in pinned} == {
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
