# F-09b. Review

- Reviewed range: `main..feat/F-09b-model-comparison` at `f6451e0`
- Reviewer: `reviewer` agent, fresh context
- Evaluation:
  - [2026-11-02-model-comparison.md](../../evals/2026-11-02-model-comparison.md): five models, each run passing calibration at 97.9 % / 95.9 %;
  - [2026-11-02-answer-baseline-qwen3-5-9b.md](../../evals/2026-11-02-answer-baseline-qwen3-5-9b.md): the default passes its gate.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

All 11 findings were confirmed against the code; none was dropped.

Finding 3 is kept with corrected reasoning. The test fixes the model to `qwen3.5-9b`, so it never guarded other models. The point that stands is that at temperature 0 the outcome is the same on every run, so the xfail need not be lenient.

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `frontend/src/features/models/ModelSelect.tsx:16-17`, `frontend/src/features/chat/ChatView.tsx:17` | The page loads while the default model's server is down. The dropdown shows the first listed model, but `ChatView` sends no model, so the API sends the question to the default, which does not answer, and no notice appears. Only a model that leaves the list after being shown triggers `onChange`. | AC-6, spec "Model list" | fix |
| 2 | minor | `evals/harness/run.py:73` | `DEFAULT_CHAT_MODEL` repeats the default of `Makefile:32` and `.env.example`. No test ties them together, so a later change of default can switch off the 75 % floor without anyone noticing. | TEST-24, ADR 0026 §5 | fix |
| 3 | minor | `backend/tests/integration/test_local_agent.py:124-130` | The checklist-note test is `xfail(strict=False)` although the outcome is the same on every run. If the model starts saving the note, the test does not fail, so nobody is told to remove the marker. | TEST-06 | fix |
| 4 | minor | `evals/harness/memory.py:109, 151-153` | `lsof` and `footprint` run without a timeout, and the sampler thread is joined without a bound. A hung `footprint` leaves the answer run hanging with no report. | AI-22 | fix |
| 5 | minor | `backend/src/assistant/adapters/pinned_models.py:171` | `LLM_MODELS` is read only by tests. It is a second list of served models beside `CHAT_MODELS`, and the two can drift apart. | | fix |
| 6 | minor | `docs/adr/0025-gemma-4-judges-without-thinking.md:36` | The Gemma 4 hash is cut short as `3eca3b8f…49e70e`; the pin ends in `…eca51d`. | AI-40 | fix |
| 7 | minor | `README.md:119` | The README still gives the old judge's size for `make judge-models` (about 18.6 GB); Gemma 4 is 14.4 GB. It also does not mention `JUDGE=qwen3.6-35b-a3b`. | | fix |
| 8 | note | `evals/harness/memory.py:76-78`, the comparison record, `README.md:24-30` | Peak memory is in MiB but labelled MB, and the record and README turn it into GB by dividing by 1000. The 24 GB limit compares mixed units. The choice does not change, because each model is on the same side of the limit either way. | | fix |
| 9 | note | `README.md:30` | Bonsai's median first token of 2.85 s is shown as 2.8 s, which understates how close it is to the 3 s limit. | | fix |
| 10 | note | `backend/src/assistant/adapters/openai_compatible_chat.py:118-125` | Concurrent availability checks are not deduplicated, so each one asks the server for `/v1/models` while another check is still running. This is harmless at one tab and a 10 s refresh. | | reject: harmless at one tab and a 10 s refresh |
| 11 | note | `docs/adr/0024-candidate-models-and-llama-cpp-upgrade.md:3`, `docs/adr/README.md` | ADR 0024's status does not say that ADR 0026 removed two of its pins. | | fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution
| # | Commits |
|---|---|
| 1 | `832375c` test, `0c5a1db` fix |
| 2 | `aef40c5` test, `0c90cb4` fix |
| 3 | `e04a784` test (test-only, no code change) |
| 4 | `574b3bf` test, `523dc04` fix |
| 5 | `4dfa393` test, `95cdfe2` fix |
| 6 | `69aedfc` docs |
| 7 | `69aedfc` docs |
| 8 | `b10f972` test, `e9f4722` fix |
| 9 | `69aedfc` docs |
| 11 | `69aedfc` docs |
