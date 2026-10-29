# F-06. Review

- Reviewed range: `main...feat/F-06-openai-compatible-chat` at `ee02d15`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-29-answers-qwen3-8b.md](../../evals/2026-10-29-answers-qwen3-8b.md). First answer baseline:
  - cites an expected passage 86.4 %;
  - language match 100 %;
  - valid on the first try 100 %;
  - out-of-scope refused 3/3;
  - time to first token 866 ms median, 1558 ms p95.
- Checks:
  - `make check`, `make test-integration` (including Qwen3 8B), `make e2e` and `make eval-answers` pass;
  - red commits precede green ones, and no green commit edits a test.
- Verification:
  - all 23 findings confirmed against the code; none dropped;
  - the reviewer reproduced findings 1, 2 and 11 against a stub server.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `adapters/openai_compatible_chat.py:356`, `:260` | A non-JSON `data:` line or completion body raises `JSONDecodeError` out of the generator; the stream is cut with no `error` or `end` event. | AC-2, AC-3, AI-21 || fix |
| 2 | major | `domain/answers.py:169`, `services/questions.py:116-123` | Text streams only when the object starts with `"answer"`. A server that writes `citations` first gives a valid answer with no text shown. | AC-1, ADR 0003 || fix |
| 3 | major | `openai_compatible_chat.py:104`, `:198`, `:263-276` | The timeout is per read, not per call, and no `max_tokens` is sent. A runaway generation can hold the answer for minutes. | AC-3, AI-22 || fix |
| 4 | major | `services/questions.py:120,130`, `openai_compatible_chat.py:189-238` | Usage reaches only the `end` event. A failed answer drops its usage, `call_tools` records none, and nothing is logged. | AI-60, AI-53 || fix |
| 5 | major | `openai_compatible_chat.py:51`, `adapters/chat_models.py:15-25` | Only the tools capability is declared. JSON schema and streaming are always assumed, and the server URL is global rather than per model. | spec scope, AI-23, ADR 0021 §5 || fix: `json_schema` and `streaming` flags; a server URL per model goes with F-09's second model |
| 6 | major | `openai_compatible_chat.py:133-135`, `:342-347` | The retry instruction and the user-message template are string literals in code. | AI-30 || fix |
| 7 | minor | `openai_compatible_chat.py:344` | Passage text is not escaped, so a document containing `</passage>` can break out of its block. | AI-10 || fix |
| 8 | minor | `openai_compatible_chat.py:333-337` | Every non-200 status becomes `model_unreachable`. A 400 for too long a prompt tells the user the model is not reachable. | AC-3 || fix |
| 9 | minor | `openai_compatible_chat.py:172-186` | `_attempt` builds the timeout and unreachable messages inline instead of using the helpers `_complete` uses. | – || fix |
| 10 | minor | `ports/chat_model.py:30-41`, `tests/contract/` | `ToolCallingModel` has no fake and no contract test; the plan put tool calls in the contract. | AC-5, ADR 0002 || fix |
| 11 | minor | `domain/answers.py:222,227` | A malformed `\u` escape raises `ValueError` from the extractor and cuts the stream. | AI-21 || fix |
| 12 | minor | `backend/pyproject.toml:99-120` | `httpx` is not in the `framework-free-core` forbidden modules, so services could call a model server directly. | ADR 0002 || fix |
| 13 | minor | `settings.py:20` | `ASSISTANT_LLM_URL` accepts any host, so passages could leave the machine without network mode. | AI-52, ADR 0004 || backlog (F-10): with the Qdrant URL guard |
| 14 | minor | `evals/harness/answers.py:181`, evaluation record | Reports give aggregates and missed cases only. AC-6 asks for per-case results. | AC-6 || fix |
| 15 | minor | `spec.md:24,40` | The spec says `make eval` runs the answer suite; it is `make eval-answers`. | AC-6 || fix |
| 16 | minor | `evals/harness/answers.py:73-85` | The stop-word lists hold words both languages use (`to`, `do`). | – || fix |
| 17 | minor | `evals/promptfoo/answers.yaml:1` | The comment names `harness/answer_run.py`, which does not exist. | – || fix |
| 18 | minor | `evals/harness/gate.py:8`, `run_answers` | No test covers `answer_failed` as lower-is-better or the answer gate. | TEST-09 || fix |
| 19 | note | `tests/integration/test_local_llm.py:13` | The plan asked for an `llm` marker; the test uses `integration` with a `skipif` probe instead. | – || fix |
| 20 | note | `.env.example:27`, `settings.py` | `.env.example` sets `qwen3-8b` while the code default is `fake-extractive`. A fresh setup fails until `make llm` runs, and the intent is not stated. | – || fix |
| 21 | note | `adapters/chat_models.py:19,25`, `Makefile` | `ChatModelSpec.pinned` is unused at runtime, and the Makefile repeats the model path. | – || fix |
| 22 | note | `adapters/chat_models.py:60` | A malformed `/v1/models` body raises `ValueError` or `KeyError` instead of `ChatModelNotReady`. | AC-4 || fix |
| 23 | note | `evals/harness/gate.py` | With 22 answer cases one case is 4.5 points, so a single-case regression passes the 5-point gate. | – || fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
