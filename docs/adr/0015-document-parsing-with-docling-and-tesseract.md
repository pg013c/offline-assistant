# 0015. Parse documents with Docling and Tesseract, models fetched ahead of time

- Status: accepted, amended by [0016](0016-docling-dependencies-and-pinned-models.md) (proposed)
- Date: 2026-10-29
- Related: FR-01, FR-02, FR-03, NFR-01, NFR-05, NFR-07, F-02, ADR 0002, ADR 0004

## Context

F-02 reads PDF (text and scanned), DOCX, PNG and JPG and has to keep the layout: headings, paragraphs, tables, page numbers, reading order. Legal texts in the dataset are two-column PDFs in English and Polish, so plain text extraction mixes columns and loses the structure that chunking by article depends on. Scans and photos need OCR with good Polish (diacritics).

Layout-aware parsers use neural models. Downloaded lazily, they break the offline rule (ADR 0004). Every dependency and model needs a licence that allows this use (NFR-07).

## Decision

1. **Docling** (MIT) is the real adapter behind the document parser port. It is installed as `docling-slim` with only the extras we need: `format-pdf`, `format-docx` and `models-local` (layout and table models on PyTorch). No RapidOCR, EasyOCR, Office formats beyond DOCX, or remote services. The version is pinned in `uv.lock`.
2. **Tesseract** (Apache-2.0) does OCR, called through Docling's Tesseract CLI option, with `eng` and `pol` language data (Apache-2.0). It is a system package, not a Python dependency: `brew install tesseract tesseract-lang` on macOS, `tesseract-ocr tesseract-ocr-pol` on Debian/Ubuntu and in CI.
3. **Models:** the Docling layout model (`docling-project/docling-layout-heron`, Apache-2.0) and TableFormer (`docling-project/docling-models`, CDLA-Permissive-2.0). Optional models (picture description, code and formula, VLM pipelines) stay off.
4. **Fetched ahead of time.** `make models` downloads them with `docling-tools models download` into `ASSISTANT_MODELS_DIR/docling` and writes a manifest with each file's SHA-256. This is the only step that needs the network; the directory can be copied from removable media instead.
5. **Offline at runtime.** The adapter passes `artifacts_path`, disables remote services, and the process runs with `HF_HUB_OFFLINE=1`. At startup the API checks the manifest and that `tesseract` with `eng` and `pol` is available, and fails with the name of what is missing and the command that installs it.
6. **Isolated behind the port.** Only the adapter imports Docling; domain and services see the parser port and our own structure types (ADR 0002). Unit tests use a fake parser; the real one is tested in `tests/integration/`.

## Alternatives considered

- **PyMuPDF** – fast and good text extraction, but AGPL, which does not fit a public MIT project, and it has no layout model for reading order or tables.
- **pypdf or pdfminer.six with our own heuristics** – permissive and light, but two-column legal PDFs come out in the wrong order, tables are lost, and there is no DOCX or OCR path.
- **Marker** – good Markdown output, but GPL-3.0 code and model weights with commercial-use limits.
- **Unstructured** – many formats, but heavier, and its high-resolution layout path depends on separately licensed models; less control over pages and tables.
- **Docling's default OCR (RapidOCR) or EasyOCR** – Python-only, but their models come from Hugging Face or ModelScope and Polish recognition is weaker than Tesseract's.
- **macOS Vision via `ocrmac`** – fast and accurate on the reference Mac, but does not run on Linux, in CI, or in the `gpu` profile.

## Consequences

- Good: one parser for every input format, with page numbers, headings and tables; OCR quality for Polish is well known; nothing is downloaded at runtime.
- Bad: PyTorch makes the backend environment much larger (about 1 GB) and the first parse slower while models load. Tesseract is a system dependency that `make setup` cannot install everywhere, so the setup guide lists it.
- Bad: Docling updates change the parse output; chunk-id stability (F-02 AC-4) is protected by integration tests on fixed fixtures, run on every Docling upgrade.
- Testing: integration tests with the real parser need the models and Tesseract, so they run with `make test-integration` and in a CI job `Integration`, not in `make check` (as with `make e2e`, ADR 0014). `testing.md` is updated in the same change.
- Follow-up: `make models` and `ASSISTANT_MODELS_DIR` in `.env.example`; README setup and the licence list (NFR-07); CI job `Integration` with Tesseract installed and models cached; `docs/architecture.md` updated with the parser adapter.
