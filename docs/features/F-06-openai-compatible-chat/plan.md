# F-06. Plan

- Status: approved
- Spec: [spec.md](spec.md)
- ADR: [0021](../../adr/0021-llama-server-and-qwen3-8b.md)

## Research

- **Port:** `ChatModel.stream_answer(question, passages)` streams plain text (`ports/chat_model.py:7-22`). It has no structured output, no error type and no metrics.
- **Service:** `QuestionService.ask` (`services/questions.py:88-125`) relays the text and then always cites `passages[0]`. The model's citations must replace that.
- **API stream:** `POST /api/chat` sends `data: <json>` lines with a `type` discriminator: `text`, `citation`, `end` (`api/schemas.py:74-115`, `api/routes/chat.py:24-51`). An exception mid-stream cuts the response, and no error is reported inside it.
- **UI:** `useChatStream.ts` is the only parser.
  - It drops unknown types (`:53-60`).
  - A stream that ends without `end` becomes "stopped before it was complete" (`:94-96`).
  - `ChatView.tsx` renders the text, the citations and an error alert.
  - Tests use msw with `sse()` helpers; the Playwright journey asserts `fake-extractive`.
- **Composition:**
  - `CHAT_MODELS` maps names to classes built with no arguments (`app.py:42, 94`). A real adapter needs a factory with settings.
  - Startup checks follow `QdrantChunkIndex.connect`: they catch `httpx.HTTPError`, name the variable and give the make target.
- **httpx:** imported at runtime by the Qdrant adapter, but declared only for tests. ADR 0021 declares it.
- **Evaluation:** Promptfoo's HTTP provider buffers the whole body.
  - An SSE answer can be read from the text in `transformResponse`.
  - Promptfoo cannot see the time to the first token, so the API reports its own timings in the `end` event (AI-60).
  - Reusable from the retrieval harness: corpus checks, API start and stop, indexing, Promptfoo command, the gate's tolerance logic and the report shape.
- **Prompts:** `backend/src/assistant/prompts/` does not exist yet (AI-30).
- **Risks:**
  - streaming a field out of JSON as it is generated (escapes split across chunks);
  - Qwen3's thinking output;
  - llama-server's JSON-schema support for nested arrays;
  - the 3 s first-token budget with three passages in the prompt.

## Design

### Domain

- **`domain/answers.py`:**
  - `ModelAnswer(text, cited: tuple[int, ...])`, the validated structured answer, with passages numbered from 1;
  - `parse_answer(raw, passage_count) -> ModelAnswer`, which raises `InvalidAnswer(reason)` for malformed JSON, an empty answer, no citations, or a passage number out of range;
  - `AnswerTextExtractor`, which takes JSON chunks and returns the newly decoded text of the `answer` string.
- **New events:**
  - `AnswerDiscarded(reason)`;
  - `AnswerFailed(code, message)`, where `code` is `invalid_answer`, `model_unreachable` or `model_timeout`;
  - `AnswerEnd` gains `usage`: prompt and completion tokens, time to first token, total time and attempts.

### Port

```python
class ChatModel(Protocol):
    model_id: str
    is_test_model: bool
    def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]: ...
```

- `ModelEvent` is one of `TextDelta`, `AttemptDiscarded`, `Answered(ModelAnswer, Usage)` or `ModelFailed(code, detail)`.
- The adapter owns the retries, because it holds the conversation.
- F-07's tool calls get their own method, `call_tools(messages, tools)`. The contract covers it, but nothing in the answer path uses it yet.

### Adapter

`adapters/openai_compatible_chat.py`, `OpenAICompatibleChat(base_url, served_model, capabilities, timeout, max_retries)` over httpx:

- `POST /v1/chat/completions` with `stream: true` and `response_format: json_schema`;
- the system prompt comes from `prompts/answer.md`, with passages in delimited blocks;
- on `InvalidAnswer` it sends the error back and retries;
- connection errors and timeouts become `ModelFailed`;
- usage and timings come from the stream.

### Composition and operation

- **Model catalogue** (`adapters/chat_models.py`): `fake-extractive`, and `qwen3-8b` with its served name, pinned GGUF and capabilities.
- **Settings:** `ASSISTANT_CHAT_MODEL`, `ASSISTANT_LLM_URL` (default `http://127.0.0.1:8080`), `ASSISTANT_LLM_TIMEOUT` and `ASSISTANT_MAX_RETRIES`.
- **Startup:** the API checks that the server answers and serves the model.
- **`make llm-models`** fetches the GGUF by hash.
- **`make llm`** starts `llama-server` with the flags of ADR 0021.

### API and UI

- **New stream events:** `discard` and `error`.
- **`end` gains** `usage`.
- **UI:**
  - `discard` clears the shown text and citations;
  - `error` shows a message per code and ends the stream.

### Evaluation

- **Dataset:** `evals/datasets/answers.yaml`, version 1. It reuses the 24 retrieval cases by id, with the expected answer language, and adds `adv-no-citations`.
- **Suite:** Promptfoo calls `/api/chat`, and `transformResponse` reduces the SSE text to the final attempt's answer, citations, failure and `usage`.
- **Metrics per run:**
  - `cites_expected`: a cited chunk among the case's expected chunks;
  - `language_match`: a stop-word check;
  - `valid_first_try`, mean `attempts`, `failed`;
  - out-of-scope refused with no model call;
  - time to first token and tokens per second, as median and p95.
- **`make eval-answers`** runs the suite against the local model, which needs `make llm`. It writes its own report and baseline, `docs/evals/answer-baseline.json`, gated by the 5-point rule only, since there are no floors yet.

## Steps

### Step 1. Structured answer in the domain

- Kind: code
- Tests first, in `tests/unit/domain/test_model_answer.py`:
  - **Valid answers:** a valid answer parses with its cited passage numbers.
  - **Rejected answers,** each raising `InvalidAnswer` with a reason:
    - malformed JSON;
    - an empty answer;
    - no citations;
    - a citation of 0 or above the passage count.
  - **The extractor:**
    - returns the answer text as it arrives, across chunk boundaries;
    - decodes escapes, including an escape or a `\u` sequence split between chunks;
    - stops at the end of the string.
- Change: `domain/answers.py`.
- [ ] red
- [ ] green

### Step 2. Port, fakes and contract

- Kind: code
- Tests first:
  - **`tests/contract/test_chat_model.py`, for every adapter:**
    - `answer` yields text deltas, then exactly one `Answered` or `ModelFailed`;
    - the joined deltas of the last attempt equal the answer text;
    - citations are within the given passages;
    - `model_id` and `is_test_model` are set.
  - **Fakes:**
    - `fake-extractive` cites passage 1;
    - a scripted fake replays attempts, failures and usage for service tests.
- Change: `ports/chat_model.py`, `adapters/fakes/chat_model.py`.
- [ ] red
- [ ] green

### Step 3. Service uses the model's citations, retries and failures

- Kind: code
- Tests first, in `test_question_service.py`:
  - **Citations:** they follow the model's cited passages, in order, without duplicates.
  - **A discarded attempt:** gives an `AnswerDiscarded` before the retry's text.
  - **`ModelFailed`:** gives an `AnswerFailed` with its code and no citation; the stream still ends.
  - **Usage:** it reaches `AnswerEnd`.
  - **Out of scope:** no model call is made (AC-7).
- Change: `services/questions.py`, `domain/answers.py`.
- [ ] red
- [ ] green

### Step 4. Stream events in the API

- Kind: code
- Tests first, in `tests/unit/api/test_chat_api.py`:
  - **`discard`:** the event is sent.
  - **`error`:** it carries `code` and `message`, and the response stays 200 with the stream completed.
  - **`end`:** it carries `usage`.
  - **Contract:** the OpenAPI document has the new events.
- Change: `api/schemas.py`, `api/routes/chat.py`, `make api-client`.
- [ ] red
- [ ] green

### Step 5. UI handles discard and error

- Kind: ui
- Tests first:
  - **`useChatStream.test.tsx`:**
    - `discard` clears the text and citations shown so far;
    - `error` ends the stream with the code's message and no "stopped before complete".
  - **`ChatView.test.tsx`:** the error alert shows the message for each code.
- Change: `useChatStream.ts`, `ChatView.tsx`.
- [ ] red
- [ ] green

### Step 6. OpenAI-compatible adapter: streamed JSON answer, retries, errors

- Kind: code
- Tests first:
  - **Contract (step 2), against a stub OpenAI-compatible server (httpx `MockTransport`):**
    - streamed chunks become deltas;
    - the request carries the JSON schema, the prompt and delimited passages.
  - **Retries and errors:**
    - an invalid first attempt is retried with the reason in the next request;
    - after `max_retries` the result is `ModelFailed("invalid_answer")`;
    - a refused connection gives `model_unreachable`, naming the URL;
    - a timeout gives `model_timeout`.
  - **Usage:** tokens and time to first token are recorded.
  - **Integration, marked `llm`, skipped unless `make llm` is up:** Qwen3 8B answers a Polish and an English question with valid citations.
- Change: `adapters/openai_compatible_chat.py`, `prompts/answer.md`, `pyproject.toml` (httpx at runtime, `llm` marker).
- [ ] red
- [ ] green

### Step 7. Tool calls in the adapter

- Kind: code
- Tests first, in the contract against the stub:
  - `call_tools` sends the tool schemas and returns parsed calls with validated arguments;
  - invalid arguments are retried, as in AI-21;
  - a server without the tools capability is refused before any request (AI-23).
- Change: `ports/chat_model.py`, `adapters/openai_compatible_chat.py`.
- [ ] red
- [ ] green

### Step 8. Model catalogue, settings, startup and make targets

- Kind: code
- Tests first:
  - **Settings:** `chat_model` accepts the catalogue's names; the LLM URL, timeout and retries have defaults.
  - **Composition:**
    - `qwen3-8b` with no server answering fails at startup with `make llm`;
    - a server that does not serve the model fails naming it.
  - **Pin:** the GGUF pin is the revision and SHA-256 of ADR 0021.
  - **Make:** `scripts/ci` tests for `make llm-models` and `make llm` (dry run).
- Change:
  - `settings.py`, `app.py`, `adapters/chat_models.py`, `adapters/pinned_models.py`;
  - `scripts/download_models.py` (LLM group);
  - `Makefile`, `.env.example`.
- [ ] red
- [ ] green

### Step 9. Answer evaluation cases

- Kind: eval
- Add `evals/datasets/answers.yaml`, version 1, with its schema:
  - the 24 retrieval case ids with the expected answer language;
  - `adv-no-citations`.
- Dataset tests check that every id exists in the retrieval dataset and that both languages are covered.
- [ ] red

### Step 10. Answer suite in the harness

- Kind: eval (harness code with its tests)
- Tests first, in `evals/tests/`:
  - **The SSE transform:** it keeps the last attempt after `discard` and reads `error` and `usage`.
  - **The language check:** it recognises Polish and English answers.
  - **Metrics:** `cites_expected`, `valid_first_try`, attempts, failures, TTFT and tokens per second.
  - **Report and gate:** the report and the gate for the answer suite.
  - **`make eval-answers`:** it refuses to run when the LLM server is down.
- Change: `evals/promptfoo/answers.yaml`, `evals/harness/` (answers module, run entry), `Makefile`.
- [ ] red
- [ ] green

### Step 11. Measure and record

- Kind: eval
- Run `make llm` and `make eval-answers` with Qwen3 8B.
- Record `docs/evals/2026-10-29-answers-qwen3-8b.md` with:
  - per-case results;
  - the time to first token against NFR-03.
- Commit the first `answer-baseline.json`.
- If time to first token misses NFR-03 by far, or answers fail often, stop and bring the numbers to the human.
- [ ] green

### Step 12. Documentation

- Kind: setup (one `docs` commit)
- Change:
  - **`architecture.md`:** the `ChatModel` row, the answer flow, `make llm`;
  - **README:** setup, the model in the licence table, status;
  - **ADR 0007:** status line;
  - **backlog.**
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 streamed answer with the model's citations, real model named | 1, 3, 4, 6, 11 |
| AC-2 bounded retries, discard event, typed failure | 1, 2, 3, 4, 5, 6 |
| AC-3 unreachable or slow server gives a typed error | 3, 4, 5, 6 |
| AC-4 model selected by configuration, checked at startup | 8 |
| AC-5 contract tests against a stub server in CI | 2, 6, 7 |
| AC-6 answer suite and first baseline | 9, 10, 11 |
| AC-7 no model call out of scope | 3 |
