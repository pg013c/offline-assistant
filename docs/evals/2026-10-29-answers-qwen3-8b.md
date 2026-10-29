# Answers with Qwen3 8B, 2026-10-29

The first measurement of the answer suite (F-06): every retrieval question, plus one adversarial case, is asked through `POST /api/chat` and answered by a local LLM. It is the first answer baseline that `make eval-answers` gates against (`answer-baseline.json`, report `answers-20261029T211003Z.json`).

## Setup

- **Model:** Qwen3 8B, `Qwen3-8B-Q4_K_M.gguf` (ADR 0021), served by llama.cpp's `llama-server`, build `b9960-a935fbffe`.
  - Metal, 16k context, thinking off, temperature 0.
  - Structured output: `{"answer", "citations"}`, at most 2 retries.
- **Retrieval:** as in the [F-05 baseline](2026-10-29-retrieval-reranker.md): hybrid search, the BGE reranker in float16 on MPS, threshold 0.5, 3 passages per answer.
- **Inputs:**
  - corpus: 4 PDFs, verified hashes;
  - dataset: `answers.yaml` version 1, which is the 24 retrieval cases of version 2 plus `adv-no-citations`.
- **Hardware:** Apple M5 Pro, 64 GB.

## Results

| Metric | Value | Cases |
|---|---|---|
| Answer cites an expected passage (`cites_expected`) | 86.4 % | 22 |
| Answer in the question's language (`language_match`) | 100 % | 22 |
| Valid on the first try (`valid_first_try`) | 100 % | 22 |
| Failed answers (`answer_failed`) | 0 % | 22 |
| Out-of-scope questions refused, no model call | 100 % | 3 |

| Performance | Value |
|---|---|
| Mean attempts | 1.0 |
| Time to first token, median | 866 ms |
| Time to first token, 95th percentile | 1558 ms |
| Tokens per second, median | 55.3 |

**Time to first token** counts from the model call. A question first spends about 0.4 s in search and reranking (the F-05 record), so the first visible word comes after about 1.3 s (median) and 2.0 s (95th percentile). Both are within NFR-03's 3 s.

The model followed the schema every time, so no retry was needed. The **adversarial case** (`adv-no-citations`) still cited Article 6: the instruction in the question did not override the rules.

## What missed

- **`ref-article-83`.** The expected chunk is not among the passages, because its dense similarity is 0.46, under the threshold (F-05 record). The model answered that the passages do not mention Article 83, which is the right content. But the schema requires at least one citation, so it still cited three unrelated passages.
- **`ref-annex-iii`.** The Annex III passages are not in the top 3, so the model answered from articles that cite Annex III.
- **`pl-ai-literacy`.** The model answered from recital 41, on the same subject, instead of Article 4. That is a fair answer, cited to a passage the dataset does not list.

The first two are retrieval misses already known from F-05. The `ref-article-83` answer shows a gap in the answer schema: a "the passages do not answer this" reply cannot be cited honestly. The agent with tools (F-07) is where the model can search again or decline. It needs a way to answer without citations when it says the passages do not cover the question; this is recorded in the backlog for F-07.

## Next

- F-07: the agent loop with tools, and an honest "not in the passages" answer.
- F-09: other models (Bielik, larger Qwen3, Gemma 3, gpt-oss) and Claude on the same suite, and a judge for answer correctness.
