# 0016. Docling's dependencies and pinned parsing models

- Status: proposed
- Date: 2026-10-29
- Related: ADR 0004, ADR 0015 (amended), F-02, F-02 review findings 1 and 9, NFR-07, GEN-30, GEN-31, AI-40

## Context

ADR 0015 chose Docling with the `format-pdf`, `format-docx` and `models-local` extras and said its models are fetched by `make models`. Building F-02 showed that this was incomplete:

- TableFormer imports OpenCV, and Docling's OCR step needs SciPy (its `convert-core` extra); neither comes with those extras.
- Docling's own PDF text backend garbles some Polish letters in EUR-Lex PDFs; pdfium reads them correctly, so the adapter uses pypdfium2 directly.
- On Linux, PyTorch from PyPI pulls about 15 CUDA packages, several gigabytes, although the parsing models run on the CPU there.
- Docling's downloader fetches the layout model at the branch `main` and an ONNX copy we do not use. Different weights on two machines give different blocks and so different chunk ids, which F-04's evaluation datasets rely on.

## Decision

1. **Direct dependencies:**
   - `docling-slim[convert-core,format-pdf,format-docx,models-local]` (MIT);
   - `opencv-python-headless` (Apache-2.0);
   - `pypdfium2` (Apache-2.0 or BSD-3-Clause);
   - `huggingface-hub` (Apache-2.0), used by `make models`;
   - `torch` and `torchvision` (BSD-3-Clause). They are direct dependencies so that uv takes them from the CPU-only PyTorch index on Linux; macOS keeps the PyPI wheels.
2. **Pinned models.** `assistant.adapters.docling_models` pins each model repository to a commit and each file Docling loads (weights and configuration) to a SHA-256:
   - `docling-project/docling-layout-heron` at `8f39ad3c` (Apache-2.0);
   - `docling-project/docling-models` at `fc0f2d45`, TableFormer v2.3.0 (CDLA-Permissive-2.0).
3. **Checked twice.** `make models` downloads exactly those files and verifies them. The API verifies them again at startup, which takes about 0.2 s, and refuses to start if a file is missing or different.
4. Changing a pin is a reviewed code change: the CI model cache key includes the pin file, and the parser's integration tests run on the new models.

## Alternatives considered

- **Keep Docling's downloader** – simpler, but the layout model follows `main` and the manifest could only record what happened to be downloaded.
- **Check sizes instead of hashes at startup** – faster, but would not catch a different file of the same size; hashing 500 MB takes a fraction of a second on the reference machine.
- **Rely on transitive pypdfium2, huggingface-hub and torch** – fewer lines in `pyproject.toml`, but the code imports them directly (GEN-30), and uv sources apply only to direct dependencies.

## Consequences

- Good: the same `uv.lock` and the same pins give the same chunks on every machine; the models directory is 505 MB instead of 670 MB.
- Bad: updating Docling may need new pins, which `make models` reports as a hash mismatch.
- Follow-up: README licence table; ADR 0015 marked as amended by this record.
