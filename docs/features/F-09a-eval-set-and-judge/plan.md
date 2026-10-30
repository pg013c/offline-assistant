# F-09a. Plan

- Status: approved
- Spec: [spec.md](spec.md)
- ADR: [0022](../../adr/0022-local-judge-and-answer-floors.md)

## Research

- **Answer suite:**
  - `answers.yaml` (version 4) reuses the 24 retrieval cases and adds 11, so 35 cases with 30 to answer;
  - `answers.schema.json` defines the answer-only fields;
  - `harness/answers.py` scores from the SSE stream (`parse_chat_stream`), and `run.py` reads saved notes back through the API before it stops it;
  - the gate (`gate.py`) has `LOWER_IS_BETTER` and the retrieval floors only.
- **What the judge needs that the stream does not give:**
  - the full text of each cited passage, since `citation` events carry a two-sentence quote only, and `GET /api/documents/{id}/chunks` returns no text;
  - which passages each sentence cites, which `[n]` markers and the citation `number` give.
- **Tool-call validity:**
  - `call_tools` retries invalid calls and returns `ModelFailed("invalid_answer")` after the last retry;
  - the agent ends the run with that failure, and the stream cannot tell it from an invalid answer;
  - usage counts `tool_turns`, but not failed ones.
- **Serving:**
  - `make llm` and `llm-preflight` serve the pinned Qwen3 8B through `LLM_MODELS` in `pinned_models.py`;
  - `scripts/download_models.py --llm` fetches it;
  - `scripts/ci/test-make.sh` checks the Makefile's targets.
- **Risks:**
  - judge verdicts vary between runs, so the judge is called at temperature 0 and calibrated;
  - 45 cases times about 1.5k tokens is fast with an A3B model, but the run gets longer;
  - Qwen3 30B-A3B and Qwen3 8B together take about 24 GB of the 64 GB.

## Design

- **Dataset:** `answers.yaml` version 5.
  - `expected.key_points` holds a list of short statements for every answerable case. For the reused retrieval cases they sit in a `references:` map in `answers.yaml`, keyed by case id, so `retrieval.yaml` stays untouched.
  - About 12 new cases bring the suite to about 45.
- **API:** `ChunkSummary` gains `text`, the chunk's own text, for the harness (ADR 0005; `make api-client`).
- **Tool validity:**
  - a tool turn that fails after its retries ends the run with `invalid_tool_call` (a new failure code, in the API and the UI copy);
  - `Usage` gains `failed_tool_turns`;
  - validity is valid turns divided by all turns over the run.
- **Judge** (`evals/harness/judge.py`):
  - `JudgeClient(url)` posts one Chat Completions request per answer, with the prompt in `evals/prompts/judge.md` and a JSON schema: `{"correctness": "correct" | "partial" | "wrong", "reason", "sentences": [{"index", "supported"}]}`;
  - the input is the question, the key points, the numbered sentences each with their cited passages, and the passages' text;
  - an invalid reply is retried twice, then "not judged".
- **Metrics** (`answers.py`):
  - `judged_correct` counts partial as half;
  - `citation_support` is supported cited sentences over cited sentences;
  - `tool_call_validity`;
  - per-case verdicts with reasons.
  - Without a judge, the judged metrics are `None` and the report says how to start it.
- **Calibration:**
  - `evals/datasets/calibration.yaml` holds fixed answers, each with its question, key points, sentences, passages and hand verdicts;
  - every judged run judges them again and reports agreement;
  - below 85 %, the run fails.
- **Gate:** floors `citation_support` ≥ 0.90 and `tool_call_validity` ≥ 0.95 for the answer suite, listed in TEST-24.
- **Make:** `judge-models`, `judge-preflight` and `judge` (`JUDGE_PORT` 8081, alias `qwen3-30b-a3b`). `eval-answers` passes `EVAL_JUDGE_URL` when the judge answers.

## Steps

### Step 0. ADR 0022 and TEST-24

- Kind: setup, a docs commit with the ADR, its index entry and the TEST-24 floors.
- [x] done

### Step 1. Reference answers and new cases

- Kind: eval, a dataset commit of its own (TEST-22)
- Tests first, in `evals/tests/test_dataset.py`:
  - version 5;
  - 40 to 50 cases, both languages;
  - every answerable case has 1 to 4 key points (one for the single-fact injection cases);
  - the new kinds are present;
  - every reference id names a case.
- Change: `answers.yaml`, `answers.schema.json`, `harness/dataset.py` (`Case.key_points`).
- The human reviews the key points in this commit.
- [x] red
- [x] green

### Step 2. Chunk text for the harness

- Kind: code
- Tests first:
  - `tests/unit/api/test_documents_api.py`: chunks are listed with their text;
  - the OpenAPI test.
- Change: `api/schemas.py`, `api/routes/documents.py`; `make api-client`.
- [x] red
- [x] green

### Step 3. Failed tool turns

- Kind: code
- Tests first:
  - `tests/unit/services/test_agent.py`: a tool turn that fails after retries ends the run with `invalid_tool_call` and counts in `failed_tool_turns`;
  - the API and OpenAPI tests for the code and the usage field;
  - the UI error copy.
- Change: `domain/answers.py`, `services/agent.py`, `api/schemas.py`, `useChatThread`/`chatStream.ts` copy; `make api-client`.
- [x] red
- [x] green

### Step 4. The judge client

- Kind: eval
- Tests first, in `evals/tests/test_judge.py`, against a stub server:
  - the request carries the schema, the question, key points, numbered sentences and passages;
  - verdicts are parsed;
  - an invalid reply is retried, then "not judged";
  - the prompt comes from its file.
- Change: `harness/judge.py`, `evals/prompts/judge.md`.
- [x] red
- [x] green

### Step 5. Judged metrics, tool validity and the gate

- Kind: eval
- Tests first, in `evals/tests/test_answers.py`:
  - `judged_correct` with partial as half;
  - `citation_support` over cited sentences, with the passages found by citation number and chunk text;
  - `tool_call_validity`;
  - without a judge, the judged metrics are skipped and a note names `make judge`.

  In `evals/tests/test_gate.py`: the answer floors.
- Change: `harness/answers.py`, `harness/gate.py`, `harness/run.py`.
- [x] red
- [ ] green

### Step 6. Calibration and the judge's make targets

- Kind: eval and infra
- Tests first:
  - `evals/tests/test_calibration.py`: agreement for correctness and support from a calibration file; below 85 % fails the run;
  - `backend/tests/unit/adapters/test_pinned_models.py`: the judge pin as ADR 0022 says, kept out of `make models` and `make llm-models`;
  - `scripts/ci/test-make.sh`: `judge-models`, `judge-preflight` and `judge` exist and name `JUDGE_PORT`.
- Change: `harness/calibration.py`, `pinned_models.py` (`QWEN3_30B_A3B`, `JUDGE_MODELS`), `scripts/download_models.py --judge`, `Makefile`, README licence table.
- [ ] red
- [ ] green

### Step 7. First judged run, calibration labels and the record

- Kind: eval
- `make judge-models`: an 18.6 GB download, done only with the human's go-ahead. Then `make judge`, and `make eval-answers`.
- From that run I draft 20 calibration items with verdicts and reasons, in a dataset commit of their own. The human confirms or corrects them. The run is then repeated with calibration.
- Record `docs/evals/2026-10-30-answers-judged.md` and update `answer-baseline.json`.
- [ ] recorded

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 | 1 |
| AC-2 | 4 |
| AC-3 | 6, 7 |
| AC-4 | 2, 3, 5, 7 |
| AC-5 | 0, 5 |
| AC-6 | 5 |
| AC-7 | 7 |
