# Judged answers, 2026-10-30

The first answer runs graded by the judge (F-09a, ADR 0022 and ADR 0023). Report `answers-20261030T165457Z.json`, run after the review fixes, is the new answer baseline in `answer-baseline.json`. The earlier reports are `answers-20261030T120939Z.json` (before five calibration labels were corrected) and `answers-20261030T125348Z.json` (after).

**The run fails its gate on calibration:** the judge reaches the 85 % agreement bar on support, but not on correctness.

Since the review, the metrics of a judge below its bar are set apart in the report's `untrusted` section. Neither the gate nor the baseline takes them as measured, so the baseline holds no `judged_correct` or `citation_support`. The figures below are indicative only. See [Findings](#findings).

## Setup

As in the [F-07a record](2026-10-30-answers-notes.md), with these changes:

- **Dataset:** `answers.yaml` version 5, with 47 cases, 41 of them to answer. Every answerable case has 1 to 4 reference key points.
- **Judge:**
  - Qwen3 30B-A3B Q4_K_M, pinned in `pinned_models.py`;
  - served by `make judge` on port 8081 with thinking on (ADR 0023), llama.cpp build `b9960-a935fbffe`;
  - temperature 0, a JSON schema, up to 8192 tokens per verdict;
  - the answer and passages are given in escaped tags;
  - prompt `evals/prompts/judge.md`, SHA-256 `4268660f…dce0c0`.

  The report's metadata records all of this, including whether the judge thought.
- **What the judge rules:**
  - for every key point, whether the answer makes it. Correctness follows in code: all made is correct, none is wrong, otherwise partial;
  - for every cited sentence, whether its cited passages support it.
- **Calibration:** 20 fixed answers in `evals/datasets/calibration.yaml` with hand verdicts, 35 cited sentences in all. They are judged again on every run.
- **Hardware:** Apple M5 Pro, 64 GB. Qwen3 8B on port 8080 and the judge on 8081 run side by side.

## Results

| Metric | F-07a baseline (30 cases) | Before the label fix | After the label fix | After the review (baseline) | Cases | Floor |
|---|---|---|---|---|---|---|
| `cites_expected` | 86.7 % | 90.2 % | 90.2 % | 90.2 % | 41 | |
| `language_match` | 100 % | 100 % | 100 % | 100 % | 41 | |
| `valid_first_try` | 96.7 % | 97.6 % | 97.6 % | 97.6 % | 41 | |
| `answer_failed` | 0 % | 0 % | 0 % | 0 % | 41 | |
| `out_of_scope_refused` | 100 % | 100 % | 100 % | 100 % | 3 | |
| `notes_saved_when_asked` | 100 % | 100 % | 100 % | 100 % | 3 | |
| `notes_saved_unasked` | 0 % | 0 % | 0 % | 0 % | 44 | |
| `injection_followed` | 0 % | 0 % | 0 % | 0 % | 6 | |
| `judged_correct` (partial counts half) | – | 67.1 % | 64.6 % | 68.3 % (untrusted) | 41 | regression rule only |
| `citation_support` | – | 96.8 % | 100 % | 98.4 % (untrusted) | 63 sentences | 90 % |
| `tool_call_validity` | – | 100 % | 100 % | 100 % | 16 tool turns | 95 % |
| Calibration, correctness | – | 80.0 % | 80.0 % | 75.0 % | 20 | 85 % |
| Calibration, support | – | 74.3 % | 85.7 % | 91.4 % | 35 | 85 % |

**Correctness by case, after the review:** 18 correct, 20 partial and 3 wrong. The wrong ones are `ref-annex-iii`, `span-providers-and-deployers` and `adv-no-citations`. The report's case table shows each case's correctness, supported sentences and valid tool turns.

**The runs vary:** the answers are the same model's at temperature 0, but not identical between runs, and the judge's verdicts vary too. Calibration agreement on correctness moved between 75 % and 80 % with the same labels. The data-in-tags prompt change came between the last two runs.

## How the judge got here

Calibration agreement on the same 20 items:

| Judge | Correctness | Support | Time per answer |
|---|---|---|---|
| One overall verdict, thinking off | 55 % | 91 % | ~3 s |
| A verdict per key point, thinking off | 55 % | 74 % | ~3 s |
| The same, with a quote from the answer per point | 55 % | 71 % | ~3 s |
| A verdict per key point, thinking on (committed) | 75–80 % | 74–80 % | ~12 s |
| Prompt: every part of a point must be stated | 65 % | 74 % | ~12 s |
| Prompt: figures and deadlines required, qualifiers optional | 65 % | 74 % | ~12 s |

**Thinking off:** the judge credited key points the answer does not make. For example, it accepted "or 4 % of turnover" for an answer that gives only EUR 20 million. Thinking fixed most of these.

**Prompt tuning:** two stricter prompts, timeboxed, moved errors between items without raising the total. The judge became too strict where the human allows a missing qualifier, for example "and then deleted". It stayed lenient on cal-19, which does not state the 72-hour deadline. Neither prompt was kept.

## Findings

1. **The judge is below the calibration bar on correctness.**
   - It reaches 75–80 %; the bar is 85 %. The remaining misses are mostly leniency on multi-part key points (cal-09, cal-13, cal-19).
   - Agreement varies by about 5 points between runs at temperature 0, which is 1 item of 20.
   - Until the bar is met, the judge's metrics are set apart as untrusted. The backlog holds raising the agreement, before F-09b compares models.
2. **Five calibration labels were wrong, and are corrected.**
   - They were written from passages cut to 400 characters for review. With the full passages, the judge was right that these sentences are supported: cal-01 S1 and S2 (recital 20 is in the second half of the passage), cal-02 S2 and S3, and cal-03 S1.
   - The human confirmed the correction, which is a dataset commit of its own.
   - Support agreement is 85.7 % and then 91.4 %; the tuning runs measured 89–94 %.
   - After the review, the other 30 support labels were re-read against the full passages, so that corrections could go either way. None needed a change. Two are close calls and were kept as not supported, because the sentence says more than the passage: cal-02 S1 gives providers a deployer's duty, and cal-04 S1 turns an Annex III exception into a general rule.
3. **Citation support depends on the judge.**
   - The thinking-off judge measured 85.7 % in the first judged run, below the 90 % floor. The thinking judge measures 96.8–100 %.
   - The support verdicts that still disagree with the human are lenient ones: the judge calls a sentence supported that the human does not. So these figures overstate it.
   - Qwen3 8B cites a passage that does not hold the claim in about one sentence in seven by the first measure, and almost never by the thinking judge.
   - Improving citation support, and a stricter check of it, are left to a separate feature, as decided.
4. **Correctness of Qwen3 8B is about two thirds by this judge** (64.6–68.3 %, untrusted). Most misses are partial answers that make some key points and leave others out, for example the second fine tier or the copy of the data. F-09b compares other models on this measure only once the judge meets its bar.
5. **Same-family bias:** the judge and the answering model are both Qwen3. F-09c has Claude re-judge a sample to measure it.

## Timing

- A judged run took 19 minutes: 6 for the answers, then 13 for judging them and the calibration set with thinking.
- The answering model's first-token median is 0.9 s, and its 95th percentile is 6.4–6.7 s on the agent path. The first run measured 1.4 s and 9.2 s, which shows how much timing varies with the judge loaded beside it.
