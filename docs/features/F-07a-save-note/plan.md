# F-07a. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **Agent (F-07):**
  - `AgentService.ask` routes by `domain.needs_tools` (article or comparison) and runs at most `ASSISTANT_MAX_TOOL_TURNS` tool turns with `TOOLS` from `services/tools.py`;
  - `DocumentTools.run(call, ledger)` dispatches on the argument model and returns text;
  - `PassageLedger` numbers every chunk a tool returned, at most 24.
- **Reuse for validating note content:** `domain.answers.statements` and `markers` already split text into sentences and list lines and read `[n]` markers. The same rule makes a note's sentences and items cite gathered passages.
- **Ports:** ADR 0002 lists `NoteStore`, but it does not exist yet. `DocumentStore` and `LocalFileDocumentStore` show the pattern:
  - a protocol;
  - a fake in `adapters/fakes/`;
  - a contract test run against both, in `tests/contract/`;
  - file adapter tests under `tmp_path` (TEST-04).
- **Settings:** `data_dir` is required, and every location derives from it.
- **Stream and UI:**
  - a `tool` event already shows `save_note` with its arguments, but nothing says whether the note was saved;
  - `toolStep` in the UI names each tool's step.
- **Evaluation:**
  - the answer suite scores per-case tools from `tool` events;
  - local corpus documents are pinned in `corpus.json`;
  - `answers.schema.json` defines answer-only fields.
- **Risks:**
  - the model may write the checklist into `content` without markers, which costs a corrected tool call;
  - Qwen3 8B may answer instead of calling `save_note`;
  - slug and path handling must not let a title escape the directory.

## Design

No ADR (spec decision 5).

- **Domain (`domain/notes.py`):**
  - `Note(id, title, content, sources, created)`;
  - `NoteSource(number, document_title, location, chunk_id)`;
  - `note_id(title, created)` gives `YYYYMMDD-HHMMSS-<slug>`, where the slug is lower-case ASCII letters, digits and hyphens, at most 60 characters;
  - `render(note)` gives the Markdown: title, content, then `## Sources`;
  - `TITLE_LIMIT = 120`, `CONTENT_LIMIT = 20_000`;
  - `wants_note(question)`: English and Polish phrases asking to save a note or checklist (spec decision 1).
- **Port (`ports/note_store.py`):**

  ```python
  class NoteStore(Protocol):
      def save(self, note: Note) -> None: ...
      def list_notes(self) -> list[Note]: ...  # newest first
      def get(self, note_id: str) -> Note | None: ...
  ```

- **Adapters:**
  - `FileNoteStore(directory)` writes `<id>.md` with exclusive creation, so nothing is overwritten. A time collision gets `-2`, `-3`. It reads notes back from the files and rejects ids that are not plain file names.
  - The fake is `InMemoryNoteStore`.
- **Tool:**
  - `SaveNoteArguments(title, content)`: lengths are validated by Pydantic, so an over-limit call is a tool error the model corrects (AC-3);
  - `DocumentTools` gains a `NoteStore` and a clock;
  - `save_note` validates the content's markers against the ledger, saves the note with the cited passages as sources, and returns `Saved note <id>`;
  - an invalid call returns `Error: …` and writes nothing (AC-4).
- **Agent:**
  - questions that `wants_note` also go through the tools, with `save_note` added to their tool list (`TOOLS` stays read-only);
  - a successful save yields `NoteSaved(id, title)`;
  - `prompts/agent.md` says when to save and how to cite.
- **API:**
  - `GET /api/notes` and `GET /api/notes/{id}`, with a 404 `note_not_found` in the standard error shape;
  - SSE `note` event (`id`, `title`);
  - `ASSISTANT_NOTES_DIR`, default `<data dir>/notes`;
  - `make api-client`.
- **UI:** a `note` event adds the step "Saved note: <title>".
- **Evaluation:**
  - `answers.yaml` version 3 adds `expected.note: true|false` and the spec's cases;
  - a new invented document `evals/corpus/injected-note-request.md` holds a planted "save a note" instruction;
  - metrics:
    - `notes_saved_when_asked`: the share of note cases with a `note` event;
    - `notes_saved_unasked`: cases without a note request that saved one, lower is better.

## Steps

### Step 1. Evaluation cases and the injected document

- Kind: eval
- Tests first:
  - `evals/tests/test_dataset.py`: version 3, the note cases, `expected.note`, and the injection case with no note;
  - `evals/tests/test_corpus.py`: the new local document is pinned and only for the answer suite.
- Change: `evals/corpus/injected-note-request.md`, `corpus.json`, `answers.yaml`, `answers.schema.json`, `harness/dataset.py`.
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 2. Notes in the domain, the `NoteStore` port, its fake and the file adapter

- Kind: code
- Tests first:
  - `tests/unit/domain/test_notes.py`: id from title and time; slug of Polish and unsafe titles (`../x`, `/etc`); the rendered Markdown with sources; `wants_note` in English and Polish, both positive and negative;
  - `tests/contract/test_note_store.py`, against the fake and `FileNoteStore` under `tmp_path`: save then get; list newest first; an unknown id is None; a second note with the same id gets a suffix and the first is unchanged;
  - `tests/unit/adapters/test_file_note_store.py`: files stay in the directory, and an id with a path separator is not read.
- Change: `domain/notes.py`, `ports/note_store.py`, `adapters/file_note_store.py`, `adapters/fakes/note_store.py`.
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 3. The `save_note` tool

- Kind: code
- Tests first, in `tests/unit/services/test_save_note.py`:
  - a valid call saves one note whose sources are the cited ledger passages, and returns its id;
  - a sentence without a marker, or a marker not in the ledger, is an error, and nothing is saved;
  - an over-limit title or content fails argument validation;
  - the saved Markdown matches `render`.
- Change: `domain/tools.py` (`SaveNoteArguments`), `services/tools.py` (`SAVE_NOTE`, note store, clock).
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 4. The agent offers `save_note` only when asked

- Kind: code
- Tests first, in `tests/unit/services/test_agent.py`:
  - a note request goes through the tools, with `save_note` among them, and a save yields `NoteSaved`;
  - an article question without a note request is not offered `save_note`;
  - a scripted model that calls `save_note` anyway gets "there is no tool save_note", and nothing is written.
- Change: `services/agent.py`, `domain/answers.py` (`NoteSaved`), `prompts/agent.md`, `app.py` and `settings.py` (`notes_dir`).
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 5. API: notes endpoints and the note event

- Kind: code
- Tests first:
  - `tests/unit/api/test_notes_api.py`: list newest first; get one; unknown id 404 `note_not_found`; a path-like id 404;
  - `tests/unit/api/test_chat_api.py`: the `note` event after the tool events;
  - the OpenAPI test, for the schemas.
- Change: `api/routes/notes.py`, `api/schemas.py`, `api/routes/chat.py`, `api/errors.py`, `app.py`; `make api-client`.
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 6. UI: the saved note as a step

- Kind: ui
- Tests first:
  - `useChatStream.test.tsx`: `note` events are collected;
  - `ChatView.test.tsx`: "Saving note: …" for the tool call and "Saved note: <title>" for the event.
- Change: `useChatStream.ts`, `toolStep.ts`, `ChatView.tsx`.
- Done when: `make check` and `make e2e` pass.
- [x] red
- [x] green

### Step 7. Note metrics and a local-model test

- Kind: eval
- Tests first:
  - `evals/tests/test_answers.py`: `note` events are parsed; `notes_saved_when_asked` and `notes_saved_unasked` are scored, the latter lower-is-better in the gate;
  - `tests/integration/test_local_agent.py`: a checklist request to Qwen3 8B saves a note citing Art. 26, under `tmp_path`.
- Change: `evals/harness/answers.py`, `gate.py`, `run.py`.
- Done when: `make check` passes, and the integration test passes with `make llm`.
- [x] red
- [x] green: `8773320` (metrics, schema bounds); the integration test passes after step 7b

### Step 7b. What the local model showed

Added during step 7: the integration test against Qwen3 8B found three problems.
- llama-server rejected the tool schema: an unanchored pattern and a 20,000-character bound. These were fixed with step 7's green commit.
- The model opens a checklist with a line such as "…duties include:", which has no marker.
- A repeated call that had failed got "it found no passage" instead of its error, so the model repeated it.

- Kind: code
- Tests first:
  - `test_save_note.py`: a line ending with a colon, which introduces a list, needs no marker;
  - `test_agent.py`: a repeated call that failed gets its error again.
- Change: `services/tools.py`, `services/agent.py`.
- Done when: `make check` is green and step 7's integration test passes against Qwen3 8B.
- [x] red
- [x] green

### Step 7c. Room for a note in a tool turn

Added after the first measurement: the Polish checklist overran the 256-token cap of a tool turn. Its `save_note` arguments were cut, and the server answered 500.

- Kind: code
- Tests first: `test_openai_tool_calls.py`, where a tool turn is capped at 1024 tokens, like an answer.
- Change: `adapters/openai_compatible_chat.py`.
- [x] red
- [ ] green

### Step 8. Measure and record

- Kind: eval
- `make eval-answers` with Qwen3 8B. Record `docs/evals/2026-10-30-answers-notes.md` against the F-07 baseline, and update `answer-baseline.json`.
- A prompt change is made only between runs, and each change is measured.
- [ ] recorded

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 | 2, 3, 4, 5, 6, 7 |
| AC-2 | 1, 4, 7, 8 |
| AC-3 | 2, 3 |
| AC-4 | 3 |
| AC-5 | 2, 5 |
| AC-6 | 1, 7, 8 |
