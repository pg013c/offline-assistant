# F-08. Chat UI

- Status: approved
- Requirements: FR-60 to FR-62; FE-01 to FE-25; ADR 0004 (network mode shown in the UI)
- Related ADRs: 0004, 0005, 0008, 0014

## Why

The UI was built a piece at a time:

- the walking skeleton's chat (F-01);
- the document panel (F-02, F-03);
- the agent's steps and the "no answer" note (F-07);
- saved notes as steps (F-07a).

M2 ends with a chat someone can use and show:

- **FR-60:** citations that open from the answer itself;
- **FR-61:** a library of documents, and now notes;
- **FR-62:** a model selector, and a visible sign that nothing leaves the machine.

This feature finishes the UI for the demo. It does not change what the model does.

## Scope

- **Conversation:**
  - the chat keeps the questions and answers of the session in order, newest at the bottom, and a new question no longer replaces the last answer;
  - the input is cleared after asking;
  - the thread is not stored, so a reload starts empty.
- **Clickable citations (FR-60):** each `[n]` marker in an answer is a button that opens the cited passage, the same dialog as the source list. The API sends each citation with its passage number, so a marker finds its citation.
- **Library (FR-61):**
  - the side panel has two tabs, Documents (as today) and Notes;
  - Notes lists the saved notes, newest first, and opens one as read-only text with its sources;
  - a note saved during a chat appears in the list without a reload.
- **Model selector (FR-62):**
  - the API lists the models it can answer with now, naming the default and the test model;
  - the UI offers them in a selector next to the input;
  - each question is answered by the chosen model, and its answer says which model answered.
- **Offline indicator (FR-62):**
  - the header shows "Offline" while network mode is off;
  - it shows a warning badge when `ASSISTANT_ALLOW_NETWORK` is on (ADR 0004). This feature adds the setting; until F-09 nothing uses the network.
- **Journeys:** the browser journey asks two questions in one thread, opens a citation from a marker and switches to the Notes tab.

## Out of scope

- Storing conversations, follow-up questions that use earlier turns as context, and editing or deleting notes.
- Rendering Markdown as formatted text. A renderer is a new dependency, so notes show as preformatted text.
- Comparison mode and the cloud model (F-09); voice (F-13, F-14).

## Acceptance criteria

- [ ] AC-1: Given two questions asked in a row, then both questions and their answers stay on screen in order, each with its own steps, sources and model; the input is empty after each ask.
- [ ] AC-2: Given an answer with `[1]` and `[2]` markers, when the user activates a marker by mouse or keyboard, then the dialog opens on the passage cited with that number; a marker without a citation is plain text.
- [ ] AC-3: Given saved notes, when the user opens the Notes tab, then the notes are listed newest first, and choosing one shows its title, text and sources; a note saved in the chat appears in the list without a reload.
- [ ] AC-4: Given the API, then `GET /api/models` lists the models it can answer with now (id, whether it is a test model, which is the default); a chat request may name one of them, an unknown one is a 422 in the standard error shape, and none means the default.
- [ ] AC-5: Given the selector, when the user picks a model and asks, then the request names that model and the answer shows it.
- [ ] AC-6: Given `GET /api/health`, then it reports whether network mode is on; the header shows "Offline" when it is off and a visible warning when it is on.
- [ ] AC-7: Given `make e2e`, then the journey covers a two-question thread, a marker that opens its source, and the Notes tab, with `fake-extractive`.

## Decisions

Confirmed by the human on 2026-10-30.

1. **Models offered:** the configured local model when its server answers, and `fake-extractive` always, labelled as a test model. F-09 adds more models and Claude to the same list.
2. **Markers to citations:** each `citation` event gains `number`, the passage number its marker uses. The UI shows only the passages cited.
3. **The thread:** in memory only; a reload starts empty.
4. **Notes:** shown as preformatted text with their sources, without a Markdown renderer.
5. **No ADR:** `ASSISTANT_ALLOW_NETWORK` is defined by ADR 0004, and a model chosen per request changes no model behaviour of its own.

## Open questions

None.
