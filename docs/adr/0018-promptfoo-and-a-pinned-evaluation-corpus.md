# 0018. Evaluate with Promptfoo on a corpus pinned by hash

- Status: accepted
- Date: 2026-10-29
- Related: FR-42, FR-43, FR-45, AI-31, AI-61, TEST-20 to TEST-23, F-04, ADR 0004, ADR 0006

## Context

ADR 0006 says model behaviour is accepted on evaluation runs. F-04 builds the harness and starts with retrieval: questions with expected sources, scored by recall@k and MRR. From F-06 on, the same harness must judge answers with a judge model and compare several local models and Claude. The architecture already names Promptfoo and an `evals/` directory.

Results must be reproducible (AI-61): the same corpus, the same models and the same dataset version give the same numbers. The default corpus is the EU AI Act and the GDPR in English and Polish (PRD §2). The evaluation must run offline once its inputs are present (ADR 0004).

## Decision

1. **Promptfoo** (MIT) is the evaluation runner, pinned to `0.124.1` in its own pnpm project `evals/`.
   - Node 24, the version already used by the frontend.
   - It calls the API through its HTTP provider: `/api/search` now, `/api/chat` from F-06.
   - Per-case assertions in JavaScript only extract facts, such as the rank of each expected source.
2. **Metrics are computed in Python**, from Promptfoo's JSON output, by a small tested module under `evals/`. It also checks the regression gate against the recorded baseline. The arithmetic stays exact and test-first (ADR 0006), whatever the runner.
   - The harness is its own uv project, with PyYAML and jsonschema (both MIT) for the dataset and httpx (BSD-3-Clause) for the API.
3. **No network from Promptfoo:**
   - `PROMPTFOO_DISABLE_TELEMETRY=1`, `PROMPTFOO_DISABLE_UPDATE=1` and `PROMPTFOO_DISABLE_SHARING=1` are set by `make eval`;
   - results are written to local files and never shared;
   - remote-generation features are not used.
4. **Pinned corpus:**
   - the four Official Journal PDFs: Regulation (EU) 2024/1689 and Regulation (EU) 2016/679, in English and Polish;
   - pinned by SHA-256 and fetched from the Publications Office by `make eval-corpus`, the only evaluation step that needs the network;
   - reused under Commission Decision 2011/833/EU and not committed. The GDPR comes in its PDF/A-1a form, the only PDF the repository offers for it.
5. **Isolation:** an evaluation run has its own data directory, Qdrant collection prefix and port, so development data is never touched.
6. **Records:**
   - every run writes a report with metrics, missed cases, model and Qdrant versions, configuration, dataset version and hardware;
   - raw results stay out of git;
   - the baseline and published comparisons are committed in `docs/evals/`.

## Alternatives considered

- **Our own Python runner only** – simplest for retrieval, but F-06 to F-09 would rebuild what Promptfoo already does: judge-model assertions with rubrics, side-by-side model comparison and its viewer.
- **Ragas or DeepEval** – Python-native and RAG-focused, but they lean on an LLM for most metrics, which retrieval with known expected sources does not need. Their defaults also assume a cloud model.
- **Metrics inside Promptfoo assertions** – one tool fewer, but Promptfoo averages per-case scores. Metrics such as the refusal shares need their own denominators, and JavaScript there would be untested.
- **Committing the corpus** – self-contained, but adds about 7 MB of binaries the hash already identifies exactly.

## Consequences

- **Good:**
  - one harness from retrieval to model comparison;
  - numbers reproducible from pinned inputs;
  - the metric arithmetic is unit-tested.
- **Bad:**
  - Promptfoo is a large Node dependency tree, kept apart from the frontend in `evals/`;
  - a first run downloads about 7 MB of corpus and indexes 464 pages, which takes minutes.
- **Follow-up:**
  - `make eval-corpus` and `make eval`;
  - `evals/` added to the README licence table and the telemetry checklist;
  - `docs/evals/` baseline;
  - targets for retrieval proposed in an ADR after F-05;
  - a manual CI workflow in F-09.
