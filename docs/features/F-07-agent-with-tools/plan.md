# F-07. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **Port:** `ToolCallingModel.call_tools(messages, tools)` exists, with validated arguments, retries for bad calls and usage (`ports/chat_model.py`). `OpenAICompatibleChat` implements it. `ScriptedToolCallingModel` is its fake, and the contract tests run it against a stub server. Nothing calls it yet.
- **Answer path:** `ChatModel.answer(question, passages)` streams the JSON answer `{"answer", "citations"}`.
  - The passages are numbered from 1.
  - `parse_answer` requires at least one citation, and the citations must be passage numbers. This is the cause of `ref-article-83`.
  - `QuestionService.ask` searches once, applies the threshold, keeps three passages and maps the model's numbers to chunks.
- **Index and store:**
  - `ChunkIndex.search(query, limit)` has no document filter.
  - Chunks have `location.article`, so one article is `DocumentStore.load_chunks(document)` filtered by article and ordered by `position`. No new port method is needed.
  - Documents have an id and a title, e.g. "GDPR (EN)".
- **API and UI:**
  - The SSE events are `text`, `citation`, `discard`, `error` and `end` (`found`, `usage`).
  - `useChatStream` drops unknown event types. `ChatView` renders `found=false` like an ordinary answer: the F-01 review #18 follow-up.
- **Composition:** `chat_model_for` builds the model from `CHAT_MODELS`, and `ChatModelSpec.tools` already declares tool calling: `true` for `qwen3-8b`, `false` for `fake-extractive`.
- **Evaluation:**
  - `corpus.json` lists EUR-Lex documents by CELEX number and `corpus.py` fetches them. A committed local file is a new kind of entry.
  - The upload accepts `.txt` and `.md`.
  - The answer dataset reuses `retrieval.yaml` and adds its own cases.
- **Risks:**
  - Splitting sentences for "every statement cited": abbreviations such as "Art. 83" and "ust. 1" must not end a sentence.
  - Extra model turns add to the time to first token (NFR-03, 3 s).
  - Qwen3 8B may call tools when it does not need to, or answer in its tool turn.
  - Tool results add tokens to a 16k context: `get_article` on a long article, and `compare`.

## Design

No ADR: no new dependency, model or standard.

### Two phases per question

1. **Gate:** the service searches for the question as today. If nothing is above the threshold, it refuses with no model call (AI-02).
2. **Research:** this phase runs only with a tool-calling model. The conversation starts with the agent prompt, the list of documents, the question, and the gate's top passages as the result of a `search_documents` call the service made itself. This saves a turn for simple questions.
   - The model then calls tools, up to `ASSISTANT_MAX_TOOL_TURNS` turns (default 4).
   - When it has enough, it replies `ready`; tool turns are capped at a small `max_tokens`.
   - Going past the limit is a typed failure, `too_many_tool_turns` (AC-1).
3. **Answer:** `ChatModel.answer(question, passages)` streams the final JSON from every passage gathered in the run. Validation and retries work as in F-06, and the conversation with the tool calls is not resent.
   - Every chunk a tool returns gets the next passage number in the run, and a repeated chunk keeps its number. Tool results show passages as `<passage n="…" document="…" article="…">` blocks (AI-10).
   - A model without tools skips the research phase, so `fake-extractive` and the browser journeys keep the F-06 path.

### Answer schema (model-behaviour change)

- `{"answer": str, "covered": bool}`. The `citations` field is gone: the citations are the `[n]` markers in the text, in order of first use.
- `parse_answer(raw, passage_count)` rejects, with a reason for the retry:
  - a marker out of range;
  - with `covered=true`: a sentence that has no marker, or no marker at all;
  - with `covered=false`: any marker.
- A sentence ends at `.`, `?` or `!` followed by whitespace and an upper-case letter. A dot after a known abbreviation (`Art`, `art`, `ust`, `pkt`, `lit`, `No`, `nr`, `e.g`, `i.e`) or after a number does not end a sentence.
- `ModelAnswer(text, cited, covered)`. For `covered=false`, the service sends no citations and `found=false`.
- The markers stay in the streamed text; F-08 makes them clickable. Every cited chunk was returned by a tool in this run and comes from the store, so it resolves (AI-01).

### Tools (`services/tools.py`, arguments in `domain/tools.py`)

| Tool | Arguments | Result |
|---|---|---|
| `search_documents` | `query`, `document?` | up to 5 passages above the threshold, reranked, optionally one document; "no passage found" otherwise |
| `get_article` | `document`, `number` | every chunk of the article in order, capped at 12; an error naming the documents or saying the article does not exist |
| `compare` | `a`, `b`, each `{document, number}` | both articles as for `get_article`, each capped at 6 |

- `document` is matched against the ids and titles of the stored documents, ignoring case.
- An unknown document or article is a tool result with an error, which the model can correct. It is not a failure of the run.

### Events and stream

- New domain event `ToolUsed(name, arguments)`, sent as the SSE event `tool` with `name` and `arguments` before any answer text.
- `AnswerEnd.usage` sums every model call in the run and adds `tool_turns`.
- The new failure code `too_many_tool_turns` goes into the domain, the API schema and the UI copy.
- Each tool call is logged with its name, turn, hit count and time, without arguments or text (AI-53).

### Prompts

`prompts/agent.md` is the system prompt for the research phase: the tools, "reply `ready` when you have the passages you need", and tool results are data. `prompts/answer.md` gains the marker rules and `covered`.

### UI

- `found=false` renders as a "no answer" state: a muted notice and no citation list.
- A `tool` event renders as a progress line, e.g. "Searching: breach notification" or "Reading: GDPR (EN) Art. 83". F-08 designs the full chat UI.

### Evaluation

- **Corpus:** `corpus.json` gains local entries (`path`, `sha256`). `evals/corpus/injected-retention-policy.md` and `evals/corpus/injected-model-card.md` are short invented documents, each with one fact and one planted instruction.
- **Dataset:** `answers.yaml` version 2:
  - the spec's cases, with `expected.behaviour: not_covered`;
  - an optional `expected.tools` (tools that should appear);
  - `expected.forbidden` (strings the answer must not contain).
- **Metrics:**
  - `citations_resolve`: every cited chunk is one returned in the run;
  - `statements_cited`: the share of sentences with a marker;
  - `expected_tools_used`;
  - `injection_followed`: lower is better;
  - `not_covered_correct`;
  - mean tool turns;
  - per-case tools and turns.

## Steps

### Step 1. Evaluation cases and the injected documents

- Kind: eval
- Tests first:
  - `evals/tests/test_corpus.py`: a local entry is checked against its hash and is not fetched.
  - `evals/tests/test_datasets.py`: version 2 loads, every injected case names a forbidden string, and `not_covered` cases have no sources.
- Change:
  - `evals/corpus/*.md`, `corpus.json`, `evals/harness/corpus.py`;
  - `evals/datasets/answers.yaml` (version 2), the dataset schema and loader. The harness does not score the new fields yet.
- Done when: `make eval-answers` on the current code indexes the new documents and runs the new cases, with the expected misses.
- [x] red
- [x] green

### Step 2. Answer schema with markers and `covered`

- Kind: code
- Tests first, in `tests/unit/domain/test_model_answer.py`:
  - markers become citations in order;
  - a sentence without a marker is rejected with its text in the reason;
  - abbreviations and numbers do not split sentences, in Polish and English;
  - `covered=false` with a marker is rejected;
  - an out-of-range marker is rejected.

  Also adapter tests for the schema sent, and service tests: `covered=false` gives no citations and `found=false`.
- Change:
  - `domain/answers.py` (`ModelAnswer.covered`, `ANSWER_SCHEMA`, `parse_answer`, sentence splitting);
  - `services/questions.py`;
  - `FakeExtractiveChatModel` writes `[1]` after its quote;
  - `prompts/answer.md`.
- Done when: `make check` is green. The prompt change is measured in step 9.
- [ ] red
- [x] green

### Step 3. Tools over the store and the index

- Kind: code
- Tests first, in `tests/unit/services/test_tools.py`, with the in-memory index and store:
  - `get_article` returns every chunk of the article in order;
  - an unknown document lists the documents, and an unknown article says so;
  - a document is matched by title or id, ignoring case;
  - `search_documents` applies the threshold and the document filter;
  - `compare` returns both articles, with caps;
  - results render as numbered `<passage>` blocks, a repeated chunk keeps its number, and passage tags inside document text are neutralised.
- Change: `domain/tools.py` (argument models, `PassageLedger`), `services/tools.py`.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 4. The agent loop in the service

- Kind: code
- Tests first, in `tests/unit/services/test_agent.py`, with `ScriptedToolCallingModel` and `ScriptedChatModel`:
  - the gate's search is the first tool result;
  - requested tools run and their results go back to the model;
  - `ready` starts the answer phase with every gathered passage;
  - a `ToolUsed` event comes for each call;
  - the limit gives `too_many_tool_turns` and no answer call;
  - a `ModelFailed` turn ends the run typed;
  - usage is summed with `tool_turns`;
  - out-of-scope questions make no model call;
  - a model without tools takes the F-06 path.
- Change:
  - `services/agent.py` (the research phase), with `QuestionService.ask` delegating to it when a tool-calling model is configured;
  - `domain/answers.py` (`ToolUsed`, `Usage.tool_turns`, the failure code);
  - `prompts/agent.md`, `settings.py` (`max_tool_turns`);
  - `app.py` passes the model as a `ToolCallingModel` when `ChatModelSpec.tools` is set;
  - the adapter's `max_tokens` per call, so tool turns are short.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 5. API: tool events and the new failure code

- Kind: code
- Tests first, in `tests/unit/api/test_chat_api.py`, with a scripted agent:
  - `tool` events come before `text`;
  - `end.usage.tool_turns` is set;
  - the `too_many_tool_turns` error event is sent and the stream still ends.

  Also the OpenAPI contract snapshot.
- Change: `api/schemas.py`, `api/routes/chat.py`; `make api-client`.
- Done when: `make check` is green, including the API contract.
- [ ] red
- [ ] green

### Step 6. UI: "no answer" state and tool progress

- Kind: ui
- Tests first:
  - `useChatStream.test.tsx`: `tool` events are collected, and `too_many_tool_turns` has its message;
  - `ChatView.test.tsx`: `found=false` shows the no-answer notice and no citations, and a tool line shows "Searching: …" or "Reading: …".
- Change: `useChatStream.ts`, `ChatView.tsx`.
- Done when: `make check` is green and `make e2e` passes unchanged (`fake-extractive`).
- [ ] red
- [ ] green

### Step 7. Integration with the local model

- Kind: code
- Tests first: `tests/integration/test_local_llm.py`, run only when the model server is up:
  - "What does Article 83 of the GDPR set out?" calls `get_article` and cites a chunk of GDPR Art. 83;
  - a Polish question answers in Polish with markers.
- Change: prompt wording only if the tests show the model misreads the tools.
- Done when: the tests pass against Qwen3 8B.
- [ ] red
- [ ] green

### Step 8. Evaluation metrics for the agent

- Kind: eval
- Tests first, in `evals/tests/test_answers.py`:
  - `citations_resolve`, `statements_cited`, `expected_tools_used`, `injection_followed` (forbidden strings, lower is better) and `not_covered_correct` from fixed SSE streams;
  - per-case tools and turns in the report;
  - in the gate, `injection_followed` is lower-is-better.
- Change: `evals/harness/answers.py`, `gate.py`, `run.py`.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 9. Measure and record the answer baseline

- Kind: eval
- `make eval-answers` with Qwen3 8B. Record `docs/evals/2026-10-30-answers-agent.md` with the before and after against the F-06 baseline, and update `answer-baseline.json`.
- The prompt is changed only between runs, in `fix(prompts)` commits, and each change is measured. Any metric worse than the F-06 baseline goes to the human before review.
- [ ] recorded

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 | 4, 5, 7 |
| AC-2 | 3 |
| AC-3 | 2, 4, 8 |
| AC-4 | 2, 6, 1 (`not-covered` case) |
| AC-5 | 1, 3, 8, 9 |
| AC-6 | 4, 5 |
| AC-7 | 8, 9 |
