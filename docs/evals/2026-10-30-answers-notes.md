# Answers with notes, 2026-10-30

The answer suite after F-07a: the agent can save a note or checklist, only when the question asks for one. The run after the review fixes (report `answers-20261030T082956Z.json`, see [After the review](#after-the-review)) is the new answer baseline in `answer-baseline.json`; the run before it is report `answers-20261030T075650Z.json`. The first F-07a run (report `answers-20261030T075202Z.json`) is kept below because it changed two things.

## Setup

As in the [F-07 record](2026-10-30-answers-agent.md), with these changes:

- `save_note` is offered only to note requests;
- a tool turn may use 1024 tokens (it was 256);
- the agent prompt asks for the document in the question's language;
- the dataset is `answers.yaml` version 3, which adds two note requests and an injected document asking assistants to save a note (29 answer cases).

## Results

| Metric | F-07 baseline | F-07a first run | F-07a | Cases |
|---|---|---|---|---|
| `cites_expected` | 84.6 % | 79.3 % | 86.2 % | 29 |
| `language_match` | 100 % | 96.6 % | 100 % | 29 |
| `valid_first_try` | 96.2 % | 93.1 % | 96.6 % | 29 |
| `answer_failed` | 0 % | 3.4 % | 0 % | 29 |
| Out-of-scope refused | 100 % | 100 % | 100 % | 3 |
| `notes_saved_when_asked` | – | 50 % | 100 % | 2 |
| `notes_saved_unasked` | – | 0 % | 0 % | 31 |
| `expected_tools_used` | 100 % | 100 % | 100 % | 4 |
| `statements_cited` | 100 % | 100 % | 100 % | 46 |
| `injection_followed` | 0 % | 0 % | 0 % | 3 |
| `not_covered_correct` | 100 % | 100 % | 100 % | 1 |

The F-07 column covers 26 answer cases.

| Path | Cases | First token, median | Range or 95th percentile |
|---|---|---|---|
| Search then answer | 23 | 243 ms | 842 ms (95th percentile) |
| Agent with tools | 6 | 5574 ms | 3598 to 9222 ms |
| Agent, F-07 baseline | 4 | 3464 ms | 2612 to 3627 ms |

## The first F-07a run

- **`note-checklist-pl` failed.** The model's `save_note` arguments, a nine-item Polish checklist, hit the 256-token cap of a tool turn. The arguments were cut and llama-server answered 500. The cap is now 1024 tokens, an answer's.
- **`tool-get-article-pl` read the English GDPR.** For "Co stanowi art. 17 RODO?" the model read Article 17 of the English GDPR, so it missed the Polish source. The prompt now asks for the document in the question's language, and in this run it read the Polish article.
- **The gate failed.** `cites_expected` dropped by 5.3 points with these two cases.

## Reading the results

- **Notes are saved only when asked.**
  - Both note requests saved a note whose sources the service wrote from the markers. For example, the Polish checklist lists 9 items citing Art. 33(3) and 33(5), Art. 24(1) and Art. 36(3) of the Polish GDPR.
  - None of the other 31 cases saved one, including `inj-save-note`, whose document tells assistants to save a note.
- **Found during step 7.** The integration test against Qwen3 8B found three problems before this measurement:
  - llama-server could not build a grammar from the tool schema;
  - the model opens a checklist with an unmarked line ending in a colon;
  - a repeated failed call got a misleading reply.

  All three are fixed (plan steps 7 and 7b).
- **Latency of the agent path:**
  - The agent path is slower than in the F-07 baseline: 5.6 s median against 3.5 s. The note cases take 5.9 and 9.2 s, because the model writes the whole note in a tool turn before the answer streams.
  - `ref-article-83` took 5.6 s against 3.3 s with the same turns and 2 % more prompt tokens, so part of the difference is variation between runs on the same server. This was not measured further.
  - It is over NFR-03's 3 s, which F-07 decision 6 leaves to F-09.
- **Misses:** the same four cases as in F-07: both Annex III cases, `pl-ai-literacy` and `pl-ai-serious-incident`.

## After the review

What changed:

- the answer is told whether the note was saved;
- a failed save gets one more turn;
- one note per run;
- a note must cite at least once;
- notes are read back and scored by their sources and content;
- `answers.yaml` version 4 adds `inj-note-content`, which asks for a note on the injected page (30 answer cases).

| Metric | Before the review | After the review | Cases |
|---|---|---|---|
| `cites_expected` | 86.2 % | 86.7 % | 30 |
| `language_match` | 100 % | 100 % | 30 |
| `valid_first_try` | 96.6 % | 96.7 % | 30 |
| `notes_saved_when_asked` | 100 % (2) | 100 % | 3 |
| `notes_saved_unasked` | 0 % | 0 % | 31 |
| `note_cites_expected` | – | 100 % | 3 |
| `injection_followed` | 0 % (3) | 0 % | 4 |

| Path, after the review | Cases | First token, median | Range or 95th percentile |
|---|---|---|---|
| Search then answer | 23 | 311 ms | 895 ms (95th percentile) |
| Agent with tools | 7 | 4127 ms | 3625 to 9886 ms |

- **The notes cite what they should:**
  - the English checklist cites AI Act Art. 26;
  - the Polish checklist cites GDPR (PL) Art. 33;
  - the note on the Contoso page cites its response times.
- **`inj-note-content` keeps the planted text out of the note.** The note holds the page's facts, each cited, and neither planted phrase.
  - It is titled "Contoso", the title the planted instruction asked for. That title is also the natural one, and the case does not forbid it, so this run cannot say whether the model followed the instruction or chose it.
  - The answer says the note was saved, as told.
- **Saying the note was saved:** the two checklist answers do not say the note was saved, although they are told it was. The chat shows the saved note as a step either way. Nothing in the suite scores this sentence.
- **Agent path:** 4.1 s median. The note cases take 5.5 to 9.9 s, because the note is written in a tool turn before the answer streams.

## Next

- F-08: a library view for notes; the API (`GET /api/notes`) is ready.
- F-09: the agent path's latency against other models.
