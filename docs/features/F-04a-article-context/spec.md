# F-04a. Article context in the index

- Status: approved
- Requirements: FR-03, FR-05; AI-31; the F-04 baseline analysis (causes 1 and 2)
- Related ADRs: 0006, 0015, 0017, 0018

## Why

The F-04 baseline shows the two biggest causes of missed passages. Both are in what the index sees, not in how it ranks.

- **The index never sees a chunk's article number or title.** A question that names "Article 50" or "the right to data portability" cannot match the passage, because those words sit in the chunk's location, not in its text. All three exact-reference cases miss the top 10.
- **Some section titles became chunks of their own.** The Polish "Obowiązki dostawców i podmiotów stosujących…" under "SEKCJA 3" is such a chunk. It is a near-copy of questions about duties, and it outranks the articles that answer them.

This feature fixes both and measures the effect with `make eval`, before F-05 adds a reranker on top. It is a retrieval change, so it is accepted on the evaluation, not on tests alone (ADR 0006, AI-31).

## Scope

- **Indexed text:** each chunk is indexed (dense and BM25) as its context (the heading path, which holds the article label and title) followed by its text. What answers quote and the UI shows stays the chunk text alone.
- **Section titles:** a short paragraph that directly follows a heading, before any other content, and does not end like a sentence becomes part of the heading path instead of a chunk.
- **Rebuilding:** documents chunked by an earlier version of the chunker are parsed again at startup, and the index moves to a new schema version, so no stale chunk or vector survives.
- **Measuring:** the evaluation runs before and after the change. The new result is recorded in `docs/evals/` and becomes the baseline.

## Out of scope

- Reranking: F-05.
- Changes to evaluation cases. The paragraph-level question (`pl-gdpr-portability`) is revisited only after this result, in a dataset-only commit.
- Document titles in the context: titles are file names today. F-08 brings a document library with proper titles.

## Acceptance criteria

- [ ] AC-1: Given a chunk under "Article 50" with the title "Transparency obligations…", then the text indexed for it begins with that article label and title, and the chunk text returned by search and cited in answers does not.
- [ ] AC-2: Given a heading followed by a short title-like paragraph and then the article's content, then the title becomes part of the heading path and no chunk consists of it. A short paragraph that ends like a sentence or with a comma, or follows other content, stays a chunk.
- [ ] AC-3: Given documents chunked by the earlier chunker, when the API starts, then they are parsed again and indexed into the new collection, and their chunk ids follow the new chunking.
- [ ] AC-4: Given the evaluation corpus, when `make eval` runs, then each of the three exact-reference cases finds its expected chunk within the top 10.
- [ ] AC-5: Given the F-04 baseline, when `make eval` runs after the change, then no metric is more than 5 points worse, recall@3 and MRR are higher, and all out-of-scope questions still stay below the threshold. The before and after numbers are recorded in `docs/evals/`.
- [ ] AC-6: The chunk ids and locations pinned for the AI Act excerpts (F-02 snapshot) change only where the new chunking requires it, and every change is explained in its commit.

## Evaluation cases

The F-04 retrieval suite (24 cases, dataset version 2) measures this feature unchanged. The cases this feature targets:

| Id | Input | Expected |
|---|---|---|
| ref-article-50 | What does Article 50 of the AI Act require? | AI Act (EN) Art. 50 in the top 10, ideally top 3 |
| ref-article-83 | What does Article 83 of the GDPR set out? | GDPR (EN) Art. 83 in the top 10 |
| ref-annex-iii | What does Annex III of the AI Act list? | the Annex III passages |
| pl-ai-deployer-duties | Jakie obowiązki mają podmioty stosujące systemy AI wysokiego ryzyka? | AI Act (PL) Art. 26 above the "SEKCJA 3" title |
| oos-pasta (and the other out-of-scope cases) | How long should pasta boil? | still no passage over the threshold |

## Decisions

1. **Context format:** the heading path joined with " > ", a blank line, then the chunk text. Document titles stay out until F-08 gives documents real titles.
2. **Section titles:** a paragraph is a title when it directly follows a heading, before any other block under it, has at most 200 characters, and does not end with `.`, `;`, `:`, `,`, `?`, `!` or `)`.
3. **Re-parsing:** each document's chunks carry the chunker version; at startup, documents chunked by an older version are queued for parsing again.
4. **Threshold:** stays at 0.5 unless the evaluation shows an out-of-scope question crossing it; any change is recorded with the measurement.
5. **No new ADR:** what is indexed is a retrieval parameter within ADR 0017, recorded in `architecture.md` and judged by the evaluation (AI-31).
