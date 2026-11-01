# F-09b. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **Model registry:**
  - `adapters/chat_models.py` maps a name to a `ChatModelSpec` (served name, pin, capability flags).
  - `Settings.chat_model` is a `Literal` of the two names. Adding a model means touching both, so they can drift.
  - `_ensure_served` already refuses to start the API when the server does not serve the named model.
- **Pins:** `adapters/pinned_models.py` holds `QWEN3_8B` in `LLM_MODELS` and the judge in `JUDGE_MODELS`.
  - `verify_models` checks the hashes.
  - `scripts/download_models.py --llm` fetches every file in `LLM_MODELS`. With the candidates added, that would be 53 GB.
  - The four candidate files are already fetched into `data/models/llm/<org>--<repo>/`, with their hashes checked against ADR 0024.
- **Makefile:**
  - `LLM_FILE` comes from `QWEN3_8B`'s pin;
  - `make llm` hard-codes `--alias qwen3-8b` and `--reasoning-budget 0`;
  - `llm-preflight` verifies all of `LLM_MODELS`;
  - `scripts/ci/test-make.sh` pins the recipe's alias and thinking setting.
  - llama.cpp 0.8.0 (build 11960) keeps every flag in use, and adds `--reasoning off`.
- **Evaluation:**
  - `harness/run.py` hard-codes `chat_model="qwen3-8b"` for `make eval-answers`.
  - It records the server's build and model path from `/props`, and reports first-token latency and tokens per second.
  - Memory is not measured.
  - `answer_failures` compares every run with `answer-baseline.json`. A candidate's run would therefore be failed by the 5-point rule for being another model, not for a regression.
- **Model list (F-08 review #10):**
  - `app.py` builds `ChatModels` once at startup, and `ChatModels.list_models` lists every entry.
  - `useModels` fetches once with no refetch interval; `useApiHealth` shows the refetch pattern.
- **Risks:**
  - **Chat templates:** a candidate's template may handle tool calls or JSON schema poorly in llama.cpp. The comparison reports it (tool-call validity, failed answers) and does not work around it per model.
  - **Memory measurement:** on Apple Silicon, llama-server maps the model file and hands it to Metal. Resident memory may undercount the GPU's share. Step 4 checks the measure against the buffer sizes llama-server logs, and falls back to the physical footprint if they disagree.
  - **Timing noise:** the judge runs beside the answering model. The answers are generated before judging starts, so timing is taken without the judge working; it is still loaded.
  - **Memory:** Qwen3.6 (20.4 GB) and the judge (18.6 GB) fit in 64 GB only with nothing else large running.

## Design

- **One registry:** each candidate becomes a `ChatModelSpec` with its pin. `Settings.chat_model` is checked against the registry's names instead of a separate `Literal`.
- **One recipe:** `make llm LLM_MODEL=<name>` serves any registered model:
  - the file and alias come from the registry;
  - the default name is `qwen3-8b` until the choice ADR;
  - the flags are the same for every model, with thinking off through `--reasoning off`.

  `make llm-models LLM_MODEL=<name>` fetches one model, and `llm-preflight` verifies only the chosen one.
- **Evaluation per model:**
  - `make eval-answers LLM_MODEL=<name>` answers with that model.
  - The report names the model and its quantisation, and its file names carry the model name.
  - The regression rule compares a run only with a baseline of the same model. A run of another model gets its floors and calibration gate only.
- **Memory:** a small sampler in the harness:
  - it finds the process listening on the LLM port and checks that it is `llama-server`;
  - it reads that process's memory every second while the answers are generated;
  - the report adds `peak_memory_mb`.
- **Availability:**
  - the `ChatModel` port gains `is_available()`. The OpenAI-compatible adapter asks `/v1/models` with a short timeout and caches the result for a few seconds; the fake is always available.
  - `ChatModels.list_models` lists only available models, and answering with an unavailable one fails as it does now.
  - The UI refetches the list on an interval and falls back to the default when the selected model disappears.
- **Choice:** the second ADR, written after the runs, fixes the default, revises NFR-03 and sets the correctness target. A default other than Qwen3 8B is a red/green change of the defaults followed by a new baseline.

No ADR is needed before step 1. ADR 0024 covers the pins, the server and the flags.

## Steps

### Step 1. Candidates in the registry, pinned

- Kind: code
- Tests first: `backend/tests/unit/test_chat_models.py` and `test_pinned_models.py`:
  - the registry names the five models, each with a pin and tools, JSON schema and streaming on;
  - each candidate's pin has the revision and SHA-256 of ADR 0024;
  - `Settings` accepts every registry name and rejects an unknown one, naming the choices;
  - `LLM_MODELS` holds the five pins.
- Change: `pinned_models.py`, `chat_models.py`, `settings.py`, `.env.example`.
- Done when: the tests pass and `make check` is green.
- [x] red
- [x] green

### Step 2. `make llm` and `make llm-models` take a model name

- Kind: infra
- Tests first: `scripts/ci/test-make.sh`:
  - `make -n llm LLM_MODEL=<each name>` serves that model's file under its alias with `--reasoning off`, the same context and GPU flags, and no other per-model flag;
  - with no `LLM_MODEL`, it serves `qwen3-8b`;
  - an unknown name fails, listing the names;
  - `llm-preflight` names `make llm-models LLM_MODEL=<name>` when that model's file is missing.
- Change: `Makefile`, `scripts/download_models.py` (`--llm <name>`), README commands.
- Done when: the checks pass and `make check` is green.
- [x] red
- [x] green

### Step 3. The answer run is per model

- Kind: code
- Tests first: `evals/tests/test_judging.py` and `test_run.py`:
  - `default_answers_config` takes the model from `LLM_MODEL`;
  - the report's metadata names the model, its pinned file and the server build;
  - report files carry the model's name;
  - `answer_failures` applies the regression rule only when the baseline's `chat_model` is the run's, and always applies floors and calibration.
- Change: `evals/harness/run.py`, `Makefile` (`eval-answers` passes `LLM_MODEL`).
- Done when: the tests pass and `make check` is green.
- [x] red
- [ ] green

### Step 4. Peak memory of the model server

- Kind: code
- Tests first: `evals/tests/test_memory.py`, with a fake process table and a fake clock:
  - the sampler finds the `llama-server` listening on the port, and refuses another program on that port by naming it;
  - it reports the peak of its samples in MB;
  - a process that disappears ends the sampling, and the samples so far still count;
  - the report's performance section and Markdown give `peak_memory_mb`.

  One integration test, against the real server, compares the measure with the buffer sizes llama-server logs.
- Change: `evals/harness/memory.py` (new), `run.py`, `answers.py` (Markdown).
- Done when: the tests pass and `make check` is green. If the integration test shows resident memory undercounting, physical footprint replaces it in the same green commit.
- [ ] red
- [ ] green

### Step 5. A model is listed only while its server answers

- Kind: code
- Tests first:
  - a contract test that every `ChatModel` adapter has `is_available()`;
  - `test_openai_compatible_chat.py`: available when `/v1/models` lists it, unavailable on an error, a timeout or a missing name, and cached for a few seconds;
  - `test_models_service.py`: `list_models` leaves out an unavailable model and lists it again once it answers;
  - a route test of `GET /api/models` with a fake that stops answering.
- Change: `ports/chat_model.py`, `adapters/openai_compatible_chat.py`, the fake, `services/models.py`. `make api-client` only if the schema changes; it should not.
- Done when: the tests pass and `make check` is green.
- [ ] red
- [ ] green

### Step 6. The UI follows the model list

- Kind: ui
- Tests first: `frontend/src/features/models/*.test.tsx`:
  - the list is fetched again on an interval;
  - when the selected model leaves the list, the selection returns to the default, and a notice says the model stopped answering.
- Change: `useModels.ts`, `ModelSelect.tsx`.
- Done when: the tests pass and `make check` and the e2e journeys are green.
- [ ] red
- [ ] green

### Step 7. Every candidate serves and answers

- Kind: code (integration)
- Tests first: `backend/tests/integration/test_candidates.py`, marked to run only against the model the server reports:
  - the API starts against `make llm LLM_MODEL=<name>`;
  - it streams an answer with a resolvable citation;
  - it makes one valid tool call.

  Run once per candidate. A failure is recorded as a finding for the record, not worked around.
- Change: none expected. A defect in shared code found here is fixed in the green commit; a per-model workaround is not.
- Done when: the test has been run against all five, and the results are noted for the record.
- [ ] red
- [ ] green

### Step 8. Five judged runs and the published table

- Kind: eval (`/eval-run`, a `docs(eval)` commit, no red/green)
- Work:
  1. Run `make eval-answers LLM_MODEL=<name>` for each candidate with `make judge` up, each run passing its calibration gate.
  2. Write `docs/evals/2026-11-xx-model-comparison.md`. It gives one row per model with:
     - quality: judged correctness, citation support, tool-call validity, refusal, `cites_expected`, failed answers;
     - speed: first-token median and 95th percentile, tokens per second;
     - memory: peak memory;
     - setup: quantisation and file size.

     It also names the hardware, server build, settings, dataset and calibration versions, and the judge.
  3. Apply the selection rule of the spec, and run `eval-analyst` on any model that misses a floor.
  4. Summarise the record in the README.
- Done when: the record is committed with all five reports' metadata in it.

### Step 9. The choice: ADR, targets and default

- Kind: code, after `/adr`
- Work:
  1. `/adr` fixes:
     - the default and the pins kept;
     - NFR-03 revised;
     - the judged-correctness target.

     The PRD changes in the same commit.
  2. Red/green, but only when the default changes: tests assert the new default in `Settings`, `make llm`, `default_answers_config` and the README.
  3. The removed candidates leave `pinned_models.py` and the registry in that step.
  4. A baseline run of the default, with `/eval-run`, replaces `docs/evals/answer-baseline.json`.
- Done when: the ADR is accepted, the defaults follow it, and the baseline run passes its floors and calibration.
- [ ] red
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 | 1, 2, 7 |
| AC-2 | 3, 4 |
| AC-3 | 8 |
| AC-4 | 9 |
| AC-5 | 8, 9 |
| AC-6 | 5, 6 |
