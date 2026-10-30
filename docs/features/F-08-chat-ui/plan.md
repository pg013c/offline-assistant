# F-08. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **Backend:**
  - `create_app` builds one `QuestionService` around the configured chat model and, when it can call tools, one `AgentService`, stored as `app.state.answers`;
  - `chat_model_for(settings)` checks the LLM server at startup;
  - `ChatRequest` has `question` only;
  - `HealthResponse` has `status` and `version`;
  - the `citation` event is built in `QuestionService.answer` from the passage number it cites, but does not carry that number.
- **Frontend:**
  - `useChatStream` keeps a single `ChatAnswer` (text, citations, tools, notes, model, found) and replaces it on each ask;
  - `ChatView` renders that one answer with a step list, a no-answer note and a sources list, and `CitationDialog` shows a citation;
  - `DocumentPanel` uses TanStack Query through `useDocuments`;
  - `ApiStatus` shows the health in the header.
  - Tests use msw and Testing Library; the Playwright journey uploads a PDF, asks in Polish and opens the source from the list.
- **Reuse:** `citationLabel`, `toolStep`, `CitationDialog`, the generated client.
- **Risks:**
  - splitting answer text into markers must not break text that contains brackets for other reasons, such as "[sic]" or "[2018]";
  - a thread of streamed answers must still cancel a stream when a new question starts;
  - several `QuestionService`s share the index and the reranker, which are thread-safe for reads.

## Design

No ADR (spec decision 5).

- **Backend:**
  - **Models.** `ChatModels` (`services/models.py`) holds one answerer per model id: the configured model (as `AgentService` or `QuestionService`), plus `fake-extractive` when it is not the configured one. It knows the default.
    - `GET /api/models` returns `[{id, is_test_model, is_default}]`;
    - `ChatRequest` gains an optional `model`; an unknown id is a 422 `unknown_model`.
  - **Citations.** `AnswerCitation` and `ChatCitationEvent` gain `number`.
  - **Network mode.** `Settings.allow_network` (`ASSISTANT_ALLOW_NETWORK`, default false), reported as `network` by `HealthResponse`.
- **Frontend:**
  - `useChatStream` becomes `useChatThread`: a list of turns, each `{question, model, answer}`, where a new ask appends a turn and aborts the running stream.
  - `AnswerText` splits text on `[n]` and `[n, m]` markers into buttons when a citation with that number exists; other text stays plain.
  - `ChatView` renders the thread; `ModelSelect` reads `useModels()`; `NetworkBadge` reads the health.
  - `LibraryPanel` holds tabs for `DocumentPanel` and `NotesPanel`:
    - `useNotes()` lists the notes, and a note opens through `useNote(id)`;
    - the chat invalidates the notes query on a `note` event.
- **Journey:** `e2e/ask-question.spec.ts` gains a second question, a marker click and the Notes tab.

## Steps

### Step 1. Citation numbers on the stream

- Kind: code
- Tests first:
  - `tests/unit/services/test_question_service.py`: each citation carries the number its passage has in the answer;
  - `tests/unit/api/test_chat_api.py`: `citation` events have `number`;
  - the OpenAPI test.
- Change: `domain/answers.py`, `services/questions.py`, `api/schemas.py`, `api/routes/chat.py`; `make api-client`.
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 2. Models: list them and choose one per question

- Kind: code
- Tests first:
  - `tests/unit/services/test_models.py`: the configured model and the test model are listed with the default; a test-model configuration lists one model; an unknown id is an error;
  - `tests/unit/api/test_models_api.py`: `GET /api/models`; a chat request naming the test model is answered by it; an unknown model is a 422 `unknown_model`; no model means the default;
  - the OpenAPI test.
- Change: `services/models.py`, `domain/errors.py`, `api/routes/models.py`, `api/routes/chat.py`, `api/schemas.py`, `api/errors.py`, `api/dependencies.py`, `app.py`; `make api-client`.
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 3. Network mode in settings and health

- Kind: code
- Tests first:
  - `tests/unit/test_settings.py`: `ASSISTANT_ALLOW_NETWORK` defaults to off;
  - `tests/unit/api/test_health.py`: health reports `network`.
- Change: `settings.py`, `api/schemas.py`, `api/routes/health.py`, `.env.example`; `make api-client`.
- Done when: `make check` is green.
- [x] red
- [x] green

### Step 4. The chat thread

- Kind: ui
- Tests first:
  - `useChatThread.test.tsx`: two asks give two turns in order; a new ask aborts the running stream; each turn keeps its own steps, citations, notes and model; the request names the chosen model;
  - `ChatView.test.tsx`: both questions and answers stay on screen; the input is empty after asking.
- Change: `useChatStream.ts` becomes `useChatThread.ts`; `ChatView.tsx`; `Turn.tsx`.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 5. Clickable markers

- Kind: ui
- Tests first:
  - `answerParts.test.ts`: text splits into text and markers; `[1, 3]` gives two markers; `[sic]` and markers with no citation stay text;
  - `ChatView.test.tsx`: a marker opens the dialog on its citation, by click and with the keyboard.
- Change: `answerParts.ts`, `AnswerText.tsx`, `Turn.tsx`.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 6. Model selector and network badge

- Kind: ui
- Tests first:
  - `ModelSelect.test.tsx`: the models are listed, the default is chosen, and the test model is labelled;
  - `ChatView.test.tsx`: a chosen model goes with the question;
  - `NetworkBadge.test.tsx`: "Offline" when network is off, a warning when it is on.
- Change: `features/models/` (`useModels.ts`, `ModelSelect.tsx`), `features/status/NetworkBadge.tsx`, `App.tsx`.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 7. Notes in the library

- Kind: ui
- Tests first:
  - `NotesPanel.test.tsx`: the notes are listed newest first; choosing one shows its title, text and sources; an empty list says so;
  - `LibraryPanel.test.tsx`: the tabs switch between Documents and Notes, from the keyboard too;
  - `useChatThread.test.tsx`: a `note` event refreshes the notes list.
- Change: `features/notes/` (`useNotes.ts`, `NotesPanel.tsx`), `features/library/LibraryPanel.tsx`, `App.tsx`.
- Done when: `make check` is green.
- [ ] red
- [ ] green

### Step 8. The browser journey

- Kind: ui
- Tests first: in `e2e/ask-question.spec.ts`:
  - two questions in one thread;
  - a marker opens the source;
  - the Notes tab shows that there are no notes, since `fake-extractive` saves none.
- Change: only what the journey shows is missing.
- Done when: `make e2e` passes.
- [ ] red
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 | 4, 8 |
| AC-2 | 1, 5, 8 |
| AC-3 | 7, 8 |
| AC-4 | 2 |
| AC-5 | 2, 4, 6 |
| AC-6 | 3, 6 |
| AC-7 | 8 |
