"""Models load one at a time.

Loading through transformers patches torch globally for a moment, so a model loading on
another thread can come out as empty "meta" tensors (seen in CI with the reranker warming
up while Docling parsed). The libraries are replaced by fakes here, so nothing real loads.
"""

import sys
import threading
import time
import types
from collections.abc import Callable
from pathlib import Path

import pytest

from assistant.adapters.bge_reranker import BgeReranker
from assistant.adapters.docling_parser import DoclingDocumentParser
from assistant.adapters.sentence_transformer_embedder import SentenceTransformerEmbedder


class Loads:
    """Counts how many fake loads run at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running = 0
        self.most = 0
        self.total = 0

    def load(self) -> None:
        with self._lock:
            self.running += 1
            self.total += 1
            self.most = max(self.most, self.running)
        time.sleep(0.05)
        with self._lock:
            self.running -= 1


@pytest.fixture
def loads(monkeypatch: pytest.MonkeyPatch) -> Loads:
    counter = Loads()

    class FakeModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            counter.load()

    class FakeConverter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def initialize_pipeline(self, *args: object) -> None:
            counter.load()

    def module(name: str, **attributes: object) -> None:
        fake = types.ModuleType(name)
        fake.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, fake)

    def anything(*args: object, **kwargs: object) -> None:
        return None

    mps = types.SimpleNamespace(is_available=lambda: False)
    module("torch", backends=types.SimpleNamespace(mps=mps), float16="float16", float32="float32")
    module("sentence_transformers", SentenceTransformer=FakeModel, CrossEncoder=FakeModel)
    module("docling.backend.pypdfium2_backend", PyPdfiumDocumentBackend=object)
    module(
        "docling.datamodel.base_models", InputFormat=types.SimpleNamespace(PDF=1, DOCX=2, IMAGE=3)
    )
    module(
        "docling.datamodel.pipeline_options",
        PdfPipelineOptions=anything,
        TesseractCliOcrOptions=anything,
    )
    module(
        "docling.document_converter",
        DocumentConverter=FakeConverter,
        ImageFormatOption=anything,
        PdfFormatOption=anything,
    )
    return counter


def test_the_embedder_the_reranker_and_docling_never_load_at_the_same_time(
    loads: Loads, tmp_path: Path
) -> None:
    starts: list[Callable[[], object]] = [
        SentenceTransformerEmbedder(tmp_path)._get_model,
        BgeReranker(tmp_path)._get_model,
        DoclingDocumentParser(tmp_path)._get_converter,
    ]
    threads = [threading.Thread(target=start) for start in starts]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert loads.most == 1
    # Docling's models load when its converter is built, not halfway through a document.
    assert loads.total == 3
