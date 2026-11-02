# F-09b. Comparison of local models

- Status: approved
- Requirements: FR-40, FR-44, FR-45; NFR-03; PRD §9 quality targets; AI-40, AI-61
- Related ADRs: 0004, 0007, 0021, 0022, 0023

## Why

ADR 0021 made Qwen3 8B the default so the pipeline could be built, not because measurements showed it was the best choice. FR-40 fixes the model versions in an ADR after the first evaluation run, and NFR-03 revises its targets once there is a measured baseline. F-09a provided the measures: judged correctness, citation support and tool-call validity, graded by a calibrated judge. Since Qwen3, newer open models have appeared, among them mixtures of experts and ternary models. This feature runs five local models through the same suite on the reference Mac. It publishes their quality, speed and memory, and picks the default from the results.

## Scope

- **Candidates:** five models, each pinned by file hash (AI-40) and selectable by configuration alone (FR-40):

  | Model | Kind | File |
  |---|---|---|
  | Qwen3 8B | dense, the baseline | Q4_K_M, 5.0 GB |
  | Qwen3.5 9B | dense, its successor at the same size | Q4_K_M, 5.7 GB |
  | Qwen3.6 35B-A3B | mixture of experts, 3B active | Q4_K_M, 20.4 GB |
  | Gemma 4 26B-A4B | mixture of experts, 4B active, another family | quantisation-aware Q4_0, 14.4 GB |
  | Ternary-Bonsai-2 27B | ternary Qwen3.8 27B | Q2_0, 7.6 GB |

- **Server:** llama.cpp from Homebrew, upgraded to a build that serves all five. Qwen3 8B is measured again on that build, so all rows share one server.
- **Settings:** every model is served in its fastest mode, with thinking off wherever the model allows it. Every model gets the same prompts, tools, context size and temperature.
- **One suite, one judge:** every candidate answers the answer suite of F-09a. The same calibrated judge grades every answer, and each run must pass its calibration gate.
- **Performance (FR-44):** measured per model in the same run:
  - time to first token, median and 95th percentile;
  - tokens per second;
  - peak memory of the model server: its physical footprint, sampled every second during the run, plus the model file it maps. Resident memory was the first measure; macOS evicts a mapped model's pages under memory pressure, so it undercounted (plan step 8).
- **Published table (FR-45):** a record in `docs/evals/` with one row per model, covering quality, speed and memory. It names the hardware, the server build, the settings and the judge. The README shows a summary of it.
- **Choosing the default:** the default is the model with the highest judged correctness among those that meet all of these:
  - the floors of PRD §9 and ADR 0022;
  - a median time to first token of at most 3 s (NFR-03);
  - peak server memory of at most 24 GB.

  When two models are within 5 points of each other, the faster one wins.
- **Decision:** an ADR fixes the default model and the pinned versions of the models kept (FR-40). It revises NFR-03 and sets a target for judged correctness (PRD §9). `make llm` and the answer baseline follow it.
- **Model list:** the UI lists a local model only while its server answers, not only at startup (F-08 review #10). With several models to switch between, a stale entry misleads.

## Out of scope

- Claude, as a candidate or as a second judge (F-09c).
- Other servers, such as MLX, Ollama or the PrismML llama.cpp fork for Bonsai's denser packings. They go to the backlog.
- Nemotron 3.5 (no Polish among its languages), Qwen3.8 27B dense (too slow for NFR-03 on this Mac), Qwen3.8 Flash-Next (too large, not Apache-2.0) and Ornith 1.5 (its card names neither base model nor languages).
- Fine-tuning, quantisation sweeps and prompt changes made for a single model.
- Reading annexes with the agent (F-07 review #4). It changes model behaviour and would blur the comparison, so it becomes a chore after this feature.
- Better citation support, and a stricter judge (follow-ups from F-09a).

## Acceptance criteria

- [x] AC-1: Given each candidate's name in `ASSISTANT_CHAT_MODEL`, when the API starts against its server, then it answers with that model with no code change. Each candidate is pinned by revision and SHA-256, fetched with its hash checked, and served by `make llm`. Proof: tests of the model registry and the Makefile check. Proved by: `backend/tests/unit/adapters/test_chat_models.py` (pins, names, capabilities, the registry as the only list, `Settings` names), `scripts/ci/test-make.sh` (`make llm` and `make llm-models` per name, default from the registry), `backend/tests/integration/test_candidates.py` (each kept model streams a cited answer and makes a valid tool call; run per model in step 7 and on Qwen3.5 9B at ship).
- [x] AC-2: Given a run of `make eval-answers` against a candidate, then the report gives its time to first token (median and 95th percentile), tokens per second and the server's peak memory, next to the quality measures and the server build. Proof: harness tests and the reports. Proved by: `evals/tests/test_memory.py`, `evals/tests/test_memory_server.py` (dense and mixture-of-experts), `evals/tests/test_run_preparation.py`, `evals/tests/test_answers.py`; the reports' `performance` and `llm_server` in the five comparison runs.
- [x] AC-3: Given the runs of all five candidates, each passing its calibration gate, then a record in `docs/evals/` publishes one table across them, with hardware, server build, settings, dataset version and judge, and the README summarises it. Proof: the record and the reports. Proved by: [2026-11-02-model-comparison.md](../../evals/2026-11-02-model-comparison.md), every run passing calibration at 97.9 % / 95.9 %, and the README summary table.
- [x] AC-4: Given the record, then an ADR fixes the default by the rule above, with the pinned versions. It revises NFR-03 and sets the judged-correctness target, and the PRD, `make llm` and the answer baseline follow it. Proof: the ADR, the PRD diff and `docs/evals/answer-baseline.json`. Proved by: [ADR 0026](../../adr/0026-qwen3-5-9b-is-the-default-model.md), the PRD diff in `b6a98a4` (NFR-03, §9), `chat_models.DEFAULT_CHAT_MODEL` read by `make llm` and the answer run (`scripts/ci/test-make.sh`, `evals/tests/test_judging.py`), and `docs/evals/answer-baseline.json` (Qwen3.5 9B, `f6451e0`).
- [x] AC-5: Given the chosen default, then on its baseline run it meets the floors: citation support ≥ 90 %, tool-call validity ≥ 95 % and out-of-scope refusal ≥ 90 %. Proof: the baseline report and the gate. Proved by: [2026-11-02-answer-baseline-qwen3-5-9b.md](../../evals/2026-11-02-answer-baseline-qwen3-5-9b.md): citation support 97.7 %, tool-call validity 100 %, out-of-scope refusal 100 %, judged correctness 81.7 % against its 75 % floor; the gate in `evals/tests/test_judging.py`.
- [x] AC-6: Given a local model whose server stops answering, when the UI asks for the models, then that model is no longer listed, and it is listed again once its server answers. Proof: route or service tests with a fake server. Proved by: `backend/tests/unit/api/test_models_api.py::test_a_local_model_whose_server_stops_answering_is_not_offered_until_it_answers`, `backend/tests/unit/adapters/test_openai_compatible_chat.py` (availability against a fake server), `frontend/src/features/models/ModelSelect.test.tsx` and `useModels.test.tsx`, `frontend/src/features/chat/ChatView.test.tsx` (review #1).

## Evaluation cases

There are no new cases. The comparison uses the F-09a answer suite unchanged: dataset version 5, 47 cases. Its out-of-scope, not-covered and injection cases are the adversarial part (TEST-20, TEST-21). The calibration set of 48 items also stays as it is.

## Decisions

Confirmed by the human on 2026-10-31.

1. **Candidates:** the five models above, picked after a check of Hugging Face on 2026-10-31. About 48 GB of downloads, which start once the ADR that pins them is accepted. The files are in ADR 0024.
2. **Server:** llama.cpp from Homebrew, upgraded. The build is recorded, as in ADR 0021, and no fork is used.
3. **Choosing the default:** the rule above, fixed before the runs.
4. **Memory:** the peak memory of the model server, measured as its physical footprint plus its mapped model file (revised in plan step 8, after resident memory undercounted).
5. **Follow-ups:** the model list is part of this feature, and reading annexes is a chore after it.
6. **ADRs:** one before the plan (`/adr`), covering the candidates' pins and the llama.cpp upgrade; one after the runs, covering the choice and the revised targets.

## Open questions

None.
