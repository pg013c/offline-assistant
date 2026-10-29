# Retrieval with the reranker, 2026-10-29

The measurement of F-05. The same index is searched twice:

- **reranked:** BGE reranker v2 M3 scores 30 hybrid candidates (ADR 0019);
- **hybrid:** the F-04a order.

The reranked mode is now the API's default and the baseline `make eval` gates against (`retrieval-baseline.json`, report `retrieval-20261029T160557Z.json`, measured again after the review). It replaces the [F-04a record](2026-10-29-retrieval-article-context.md).

## Setup

- **Unchanged from F-04a:**
  - the corpus: 4 PDFs, 464 pages, verified hashes;
  - the dataset: version 2, 21 in-scope and 3 out-of-scope cases;
  - the models: BGE-M3 `5617a9f6`, Docling layout `8f39ad3c`, TableFormer `fc0f2d45`;
  - Qdrant 1.20.0, threshold 0.5, top 10, Apple M5 Pro.
- **Added:** BGE reranker v2 M3 `953dc6f6`, in float16 on MPS.
- **Latency:** Promptfoo sends one request at a time, so each figure is a single search through the API: embedding, Qdrant and, when reranking, scoring.
- **Warm-up:** the API loads the reranker in the background at startup (about 8 s here), and the harness sends one unmeasured search per mode before the measured ones, reported as the warm-up request.
- **Run settings:** 30 reranked candidates, MPS, float16, recorded in the report's metadata.
- **Indexing:** the corpus took 102.1 s; reranking does not touch indexing.

## Results

| Metric | Hybrid (F-04a) | Reranked | Change | Cases |
|---|---|---|---|---|
| recall@3 | 90.5 % | 95.2 % | +4.8 | 21 |
| recall@10 | 100.0 % | 100.0 % | 0 | 21 |
| MRR | 0.821 | 0.873 | +0.052 | 21 |
| Out-of-scope questions with no passage over the threshold | 100.0 % | 100.0 % | 0 | 3 |
| In-scope questions with no passage over the threshold | 0.0 % | 0.0 % | 0 | 21 |
| answerable@3 | 90.5 % | 90.5 % | 0 | 21 |
| Search latency, median | 27 ms | 410 ms | +383 ms | 24 |
| Search latency, 95th percentile | 30 ms | 473 ms | +443 ms | 24 |
| Warm-up request | 27 ms | 399 ms | | 1 |
| Top out-of-scope similarity | 0.38 | 0.38 | 0 | 3 |

**answerable@3** counts a case when an expected chunk is among the first three hits at or above the threshold: the passages an answer can use. It was added after the review. On this dataset the reranker does not change it.

- **What it changes:** the order within the passages an answer uses. The cited passage is the first of them.
- **Why `ref-article-83` gains nothing for answers:** it ranks first with the reranker, but its dense similarity is 0.46, under the threshold, so an answer cannot use it. That fits the test removed in `2152e76`, where the model preferred a passage citing Article 83 when the question named only the number.

The top out-of-scope similarity is the highest dense similarity of any out-of-scope question's hits. It is now in the report, and the 0.5 threshold still has a margin of 0.12. Refusal still depends on dense similarity, not on the reranker score (spec decision 5).

## Precision and the default

The first run used float32 (report `retrieval-20261029T150339Z.json`). It gave the same quality figures, but a median of 1342 ms and a p95 of 1599 ms. That is above the 1 s limit of spec decision 4.

Float16 on MPS (plan step 5a) left every metric and every rank unchanged and brought the p95 to 498 ms. All three conditions of decision 4 hold:

- recall@3 and MRR are higher;
- no metric is worse;
- the p95 is under 1 s.

The run after the review gives the same quality figures and a p95 of 473 ms; answerable@3 is equal in both modes. The reranker is therefore on by default (`ASSISTANT_RERANKER=on`): decision 4 holds, and better order means a better cited passage, at about 0.4 s per question. On CPU, as in Docker (ADR 0007), it runs in float32 and will be slower. F-10 measures that.

## The cases that changed

| Case | Hybrid | Reranked |
|---|---|---|
| ref-article-83 | rank 8 | rank 1 |
| ref-annex-iii | rank 9 | rank 6 |
| en-ai-fines-prohibited | rank 2 | rank 1 |
| pl-ai-literacy | rank 2 | rank 1 |
| span-access-and-rectification | rank 2 | rank 1 |
| pl-gdpr-portability | rank 1 | rank 2 |
| x-pl-to-en-annex-iii | rank 2 | rank 3 |
| pl-ai-serious-incident | rank 1 | rank 3 |

Five cases rose and three fell, all three still in the top 3. Cross-language cases kept their place, except `x-pl-to-en-annex-iii`, which fell one rank.

## What still misses

- **ref-article-83:** first with the reranker, but below the threshold (0.46), so an answer cannot use it.
- **ref-annex-iii** (rank 6). The question "What does Annex III of the AI Act list?" names the annex but not its subject. Articles that cite Annex III, such as Article 6(2) and Article 7, read as close answers to the reranker as well. A question about the subject ("Which high-risk areas does the AI Act list?") is a dataset question. The spec expected this case in the top 3. The human accepted the miss on 2026-10-29 (review finding 4), and the case moves to F-09's full evaluation set.

## Next

- Retrieval targets, proposed in an ADR with these numbers (ADR 0018 follow-up).
- Reranker latency on CPU, measured with the Docker profiles (F-10).
