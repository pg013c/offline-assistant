# Retrieval baseline, 2026-10-29

> Superseded by [retrieval with article context](2026-10-29-retrieval-article-context.md) (F-04a), which `make eval` now gates against. This record is kept as the "before" of that comparison.

The baseline of the retrieval suite (F-04) that `make eval` gated against (`retrieval-baseline.json`, PRD §9: no metric may get worse by more than 5 points). No targets yet: they are proposed in an ADR after F-05.

It was recorded after the F-04 review, on dataset version 2 and with every run indexing the corpus from scratch. The first run, on dataset version 1, is kept below for comparison.

## Setup

- Corpus: AI Act and GDPR, English and Polish (4 PDFs, 464 pages, 2,670 chunks), pinned in `evals/corpus.json` and verified before the run.
- Dataset: `evals/datasets/retrieval.yaml`, version 2, 24 cases (21 in scope, 3 out of scope).
- Retrieval: BGE-M3 (`5617a9f6`) dense and BM25 in Qdrant 1.20.0, fused by reciprocal rank, top 10; similarity threshold 0.5.
- Parsing: Docling with the layout model `8f39ad3c` and TableFormer `fc0f2d45`.
- Hardware: MacBook Pro, Apple M5 Pro, 18 cores, macOS 26.4.
- Indexing the corpus took 97.7 s for 464 pages. NFR-05 allows 5 minutes for 150 pages.

## Results

| Metric | Version 2 (baseline) | Version 1 | Cases |
|---|---|---|---|
| recall@3 | 61.9 % | 52.4 % | 21 |
| recall@10 | 81.0 % | 76.2 % | 21 |
| MRR | 0.573 | 0.422 | 21 |
| Out-of-scope questions with no passage over the threshold | 100.0 % | 100.0 % | 3 |
| In-scope questions with no passage over the threshold | 0.0 % | 0.0 % | 21 |

The difference between the versions comes from the dataset alone. Version 2 lets the four cross-language cases accept the same article in either language, because the corpus holds both versions of each act.

**How sensitive the gate is.** With 21 in-scope cases, one case moves recall by 4.76 points, so one more missed case does not trip the 5-point gate on its own. With 3 out-of-scope cases, one case moves that share by 33 points. MRR is gated on the same scale, as hundredths. The targets ADR after F-05 has to take this into account, for example by growing the set or gating on counts.

## Missed cases and why

Analysed by the `eval-analyst` agent and checked against the code. The analysis found four causes.

1. **Article numbers and titles are not in the indexed text.** The index embeds and searches `chunk.text` only. "Article 50", "Transparency obligations" or "Prawo do przenoszenia danych" live in the chunk's location and heading path, not its text.
   - Cases: `ref-article-50`, `ref-article-83` and `ref-annex-iii` miss the top 10, and `pl-gdpr-portability` misses it as well. `pl-ai-literacy` is weakened.
   - A reranker cannot fix this, since the passages are not retrieved. It needs a change to what is indexed.
2. **A section title became a chunk of its own.** The Polish "SEKCJA 3: Obowiązki dostawców i podmiotów stosujących…" (88 characters) is a near-copy of the questions about duties and ranks first for them.
   - Cases: `pl-ai-deployer-duties`, `pl-ai-literacy`, `span-providers-and-deployers`.
   - Fix: a chunking change.
3. **Neighbouring passages outrank the target.** Recitals and twin articles rank above it: Article 100(2) repeats Article 99(3) for EU bodies.
   - Case: `en-ai-fines-prohibited`, plus parts of the cases above.
   - Fix: a reranker (F-05).
4. **Paragraph granularity.** For `pl-gdpr-portability` the best hit is Article 20(2), which also answers the question. This is a debatable expectation, revisited after cause 1.

## Next

- Index the article number and title with each chunk, and stop section titles from becoming chunks (causes 1 and 2), then run again.
- Measure the reranker against this baseline (F-05).
