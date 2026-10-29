# Retrieval baseline, 2026-10-29

The first run of the retrieval suite (F-04). It sets the baseline that `make eval` gates against (`retrieval-baseline.json`, PRD §9: no metric may get worse by more than 5 points). No targets yet: they are proposed in an ADR after F-05.

## Setup

- Corpus: AI Act and GDPR, English and Polish (4 PDFs, 464 pages, 2,670 chunks), pinned in `evals/corpus.json`.
- Dataset: `evals/datasets/retrieval.yaml`, version 1, 24 cases (21 in scope, 3 out of scope).
- Retrieval: BGE-M3 (`5617a9f6`) dense and BM25 in Qdrant 1.20.0, fused by reciprocal rank, top 10; similarity threshold 0.5.
- Parsing: Docling with the layout model `8f39ad3c` and TableFormer `fc0f2d45`.
- Hardware: MacBook Pro, Apple M5 Pro, 18 cores, macOS 26.4.
- Commit `973e1a4`. The whole run, including indexing the corpus, took 1 min 44 s. Indexing the four files took under a minute, well within NFR-05 (5 min for 150 pages).

## Results

| Metric | Value | Cases |
|---|---|---|
| recall@3 | 52.4 % | 21 |
| recall@10 | 76.2 % | 21 |
| MRR | 0.422 | 21 |
| Out-of-scope questions with no passage over the threshold | 100.0 % | 3 |
| In-scope questions with no passage over the threshold | 0.0 % | 21 |

## Missed cases and why

Analysed by the `eval-analyst` agent and checked against the code. The analysis found five causes.

1. **Article numbers and titles are not in the indexed text.** The index embeds and searches `chunk.text` only. "Article 50", "Transparency obligations" or "Prawo do przenoszenia danych" live in the chunk's location and heading path, not its text.
   - Cases: `ref-article-50`, `ref-article-83` and `ref-annex-iii` miss the top 10. `pl-gdpr-portability` and `pl-ai-literacy` are weakened.
   - A reranker cannot fix this, since the passages are not retrieved. It needs a change to what is indexed.
2. **A section title became a chunk of its own.** The Polish "SEKCJA 3: Obowiązki dostawców i podmiotów stosujących…" (88 characters) is a near-copy of the questions about duties and ranks first for them.
   - Cases: `pl-ai-deployer-duties`, `pl-ai-literacy`, `span-providers-and-deployers`.
   - Fix: a chunking change.
3. **Neighbouring passages outrank the target.** Recitals and twin articles rank above it: Article 100(2) repeats Article 99(3) for EU bodies, and recitals echo the wording of articles.
   - Cases: `en-ai-fines-prohibited`, plus parts of the cases above.
   - Fix: a reranker (F-05).
4. **Cross-language cases count the same article in the question's language as a miss.**
   - `x-pl-to-en-breach` finds the Polish Article 33(1) first and the expected English one at rank 6. `x-en-to-pl-erasure` finds the English Article 17(1) first.
   - Whether the case should accept either language is a question about the dataset, to be decided in its own commit (TEST-22) after the code changes above.
5. **Paragraph granularity.** For `pl-gdpr-portability` the best hit is Article 20(2), which also answers the question. This is a debatable expectation, revisited after cause 1.

## Next

- Index the article number and title with each chunk, and stop section titles from becoming chunks (causes 1 and 2), then run again.
- Measure the reranker against this baseline (F-05).
- Review the cross-language and paragraph-level expectations in a dataset-only commit.
