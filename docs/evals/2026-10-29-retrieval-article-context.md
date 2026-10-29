# Retrieval with article context, 2026-10-29

The measurement of F-04a: each chunk is indexed with its heading path (article label and title, annex label and title), and section titles no longer become chunks. It replaces the [F-04 baseline](2026-10-29-retrieval-baseline.md) as the baseline `make eval` gates against (`retrieval-baseline.json`).

## Setup

The setup is the F-04 baseline's except for the indexed text:

- the same corpus (4 PDFs, 464 pages, verified hashes);
- the same dataset (version 2, 21 in-scope and 3 out-of-scope cases);
- the same models: BGE-M3 `5617a9f6`, Docling layout `8f39ad3c`, TableFormer `fc0f2d45`;
- Qdrant 1.20.0, threshold 0.5, top 10;
- the same hardware: Apple M5 Pro.

The index changes in two ways:

- **Chunker version 3:** section titles join the heading path, and annex labels keep their title next to them.
- **Index schema version 2:** chunks are indexed as their heading path followed by their text.

Indexing the corpus from scratch took 106.4 s.

## Results

| Metric | F-04 baseline | F-04a | Change | Cases |
|---|---|---|---|---|
| recall@3 | 61.9 % | 90.5 % | +28.6 | 21 |
| recall@10 | 81.0 % | 100.0 % | +19.0 | 21 |
| MRR | 0.573 | 0.821 | +0.248 | 21 |
| Out-of-scope questions with no passage over the threshold | 100.0 % | 100.0 % | 0 | 3 |
| In-scope questions with no passage over the threshold | 0.0 % | 0.0 % | 0 | 21 |

Out-of-scope questions reach a similarity of at most 0.38, against 0.33 before. That is still clearly below the 0.5 threshold, which stays.

The first run of F-04a, without the annex rule, gave recall@3 90.5 %, recall@10 95.2 % and MRR 0.815. In that run `ref-annex-iii` was still outside the top 10, because the annex title had replaced "ANNEX III" in the heading path. That run led to chunker version 3.

## The cases that changed

| Case | F-04 baseline | F-04a |
|---|---|---|
| ref-article-50 | not in the top 10 | rank 1 |
| ref-article-83 | not in the top 10 | rank 8 |
| ref-annex-iii | not in the top 10 | rank 9 |
| pl-gdpr-portability | not in the top 10 | rank 1 |
| pl-ai-deployer-duties | rank 5 | rank 1 |
| span-providers-and-deployers | rank 6 | rank 1 |
| en-ai-fines-prohibited | rank 4 | rank 2 |
| pl-ai-literacy | rank 4 | rank 2 |

## What still misses the top 3

- **ref-article-83** (rank 8). The question names no subject ("What does Article 83 of the GDPR set out?"). Recitals and other articles that cite Article 83 compete with its own paragraphs.
- **ref-annex-iii** (rank 9). Several articles cite "Annex III" in their text, and the question uses the same words.

A reranker that reads the question and the passage together (F-05) is the next thing to measure on both.
