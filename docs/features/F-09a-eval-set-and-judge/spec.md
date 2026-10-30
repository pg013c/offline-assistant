# F-09a. Evaluation set and judge

- Status: approved
- Requirements: FR-42, FR-43; PRD §9 quality targets; AI-12, AI-31, AI-61; TEST-20 to TEST-24
- Related ADRs: 0004, 0006, 0018, 0020, 0021

## Why

The answer suite checks whether an answer cites an expected passage, in the right language, with notes and injections handled. It cannot yet tell whether the answer is right, or whether a cited passage supports the sentence that cites it. PRD §9 sets two targets the project does not measure:

- citation accuracy ≥ 90 %;
- valid tool calls ≥ 95 %.

It also asks for judged correctness per model. FR-42 asks for 30–50 questions with expected answers.

F-09b compares local models, and F-09c adds Claude; both need these measures first. This feature builds them and measures the default model, Qwen3 8B.

## Scope

- **Evaluation set (FR-42):** the answer suite grows to about 45 cases.
  - Each answerable case gains a reference answer: one to four key points a correct answer must make (one for the single-fact injection cases).
  - New cases fill the gaps: more Polish questions, questions spanning articles, comparisons, not-covered and injection cases.
  - The existing ids stay, so earlier results remain comparable.
- **Judge (FR-43):** a judge model reads each answer with its question, reference and cited passages, and gives two verdicts:
  - **correctness:** correct, partly correct or wrong against the key points;
  - **citation support:** for each sentence, whether the passages it cites support it.

  The judge runs only in the evaluation, never in the API.
- **Calibration:** the judge is checked against verdicts written by hand on a sample of answers. Its agreement is reported, and a judge below the agreement bar is not used.
- **Measures:**
  - judged correctness, reported;
  - citation support against the 90 % target;
  - tool-call validity, the share of tool calls valid after retries, against the 95 % target.

  All three go into the report, the record and the answer baseline.
- **Record:** the first judged run of Qwen3 8B is recorded in `docs/evals/` and becomes the baseline F-09b compares with.

## Out of scope

- Other local models, memory measurements, the published comparison table and the model ADR (F-09b).
- Claude as a model or as a second judge (F-09c).
- Changing prompts or retrieval to improve the new measures. This feature only measures; improvements are decided after the record.

## Acceptance criteria

- [ ] AC-1: Given the answer dataset, then it holds 40 to 50 cases in both languages, every answerable case has a reference answer of key points, and the new cases include Polish, multi-article, comparison, not-covered and injection questions; the dataset validates against its schema.
- [ ] AC-2: Given an answer, its question, reference and cited passages, when the judge runs, then it returns a correctness verdict and a support verdict per cited sentence as validated structured output; an unreadable judge reply is retried and then recorded as "not judged", never as a pass.
- [x] AC-3: Given the hand-labelled sample, then the report gives the judge's agreement with it, for correctness and for support; a judge below the agreed bar fails the run. Proved by `evals/tests/test_calibration.py`, `evals/tests/test_judging.py` and report `answers-20261030T180237Z.json` (85.4 % and 90.5 % on 48 items).
- [ ] AC-4: Given `make eval-answers` with the judge available, then the report gives, per case and overall:
  - judged correctness;
  - citation support;
  - tool-call validity.
- [ ] AC-5: Given citation support and tool-call validity, then the gate fails a run below their PRD targets (90 %, 95 %) or more than 5 points worse than the baseline; judged correctness is reported and compared, not floored.
- [ ] AC-6: Given the judge is not running, then `make eval-answers` still runs the unjudged metrics and says the judged ones were skipped, naming the command that starts the judge.
- [ ] AC-7: Given the first judged run of Qwen3 8B, then it is recorded in `docs/evals/` with the judge's identity and calibration, and becomes the answer baseline.

## Evaluation cases

The new cases are listed in the dataset commit; their kinds:

| Kind | About | Example |
|---|---|---|
| reference answer | every answerable case | `en-gdpr-breach-72-hours`: notify the supervisory authority; without undue delay; within 72 hours where feasible; reasons for any delay |
| Polish, multi-article | GDPR Arts 15 and 16 together | Polish answer citing both |
| comparison | AI Act vs GDPR on fines | `compare` or two lookups |
| not-covered | a related question the corpus does not answer | "not covered", no citation |
| injection | a planted instruction in a passage the answer must cite | cites it, does not follow it |

## Decisions

Confirmed by the human on 2026-10-30.

1. **Judge:** a larger local model than the one judged, served by llama.cpp on a port of its own (`make judge`), proposed as Qwen3 30B-A3B. Its pin and its same-family bias go into an ADR, and F-09c's Claude re-judges a sample.
2. **Reference answers:** drafted as key points from the articles' text in a dataset commit of their own (TEST-22), reviewed by the human.
3. **Calibration:** 20 answers of the first run, with verdicts drafted with a one-line reason each and confirmed by the human. The agreement bar is 85 % for correctness and 85 % for support.
4. **Gate:** citation support is floored at 90 % and tool-call validity at 95 %, as PRD §9 says. Judged correctness follows the 5-point regression rule only, until F-09b. TEST-24 changes in the judge ADR.
5. **ADR:** one ADR for the judge (`/adr` before the plan).

## Open questions

None.
