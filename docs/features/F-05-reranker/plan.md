# F-05. Plan

- Status: approved
- Spec: [spec.md](spec.md)
- ADR: [0019](../../adr/0019-bge-reranker-v2-m3-for-reranking.md)

## Research

- **Search path:**
  - `QuestionService.search(query, limit)` returns `index.search` as is (`services/questions.py:53`);
  - `ask` fetches `CANDIDATES = 10`, keeps those at or above the dense `min_similarity` and takes 3.

  Reranking belongs between those two steps, in the service, behind a port. The index stays as it is.
- **Models:**
  - `pinned_models.py` lists every model with its revision and file hashes;
  - `scripts/download_models.py` fetches everything in `PINNED_MODELS`;
  - `verify_models` raises `ModelsNotReady`.

  Adding the reranker to the list makes `make models` fetch it. The CI model cache key already hashes `pinned_models.py`.
- **Adapter pattern:** `SentenceTransformerEmbedder` loads lazily under a lock, picks MPS or CPU, loads with `local_files_only` and has `ensure_ready`. The reranker adapter copies this, with sentence-transformers' `CrossEncoder`.
- **Composition:**
  - `build_adapters` checks each model before wiring it;
  - `document_parser_for(settings)` shows how a setting selects an adapter;
  - `schema_adapters()` needs nothing outside the process.
- **API:**
  - `POST /api/search` takes `query` and `limit` and returns a list of `SearchHit` with `similarity`;
  - adding an optional request field and a nullable hit field keeps the contract backwards compatible.
- **Evaluation:**
  - Promptfoo calls `/api/search` through one provider;
  - `hits_by_case` reads ranked hits per case;
  - metrics, report and gate assume one set of results;
  - Promptfoo records `latencyMs` per result and runs 4 requests at once, which would distort latency.
- **Risks:**
  - 2.3 GB more model, and its first load takes seconds;
  - 30 pairs per question add latency, measured in step 6;
  - the reranker could lower cross-language cases, which the evaluation shows per case.

## Design

### Domain and ports

- **`ports/reranker.py`:**

  ```python
  class Reranker(Protocol):
      model_id: str
      def score(self, query: str, passages: Sequence[str]) -> list[float]: ...
  ```
- **`domain`:** `rerank(found, scores)` orders the candidates by score, highest first, and keeps the hybrid order for ties.
- **Fake:** `adapters/fakes/reranker.py`, `WordOverlapReranker`, scores by shared words. It is deterministic and needs no model.

### Adapter

`adapters/bge_reranker.py`, `BgeReranker`:

- `CrossEncoder` from `models_dir / BGE_RERANKER.directory`, loaded lazily;
- `ensure_ready`;
- `model_id` is `BAAI/bge-reranker-v2-m3@953dc6f6`;
- it scores `indexed_text(chunk)`, so the reranker sees the article label and title too.

### Service

- `QuestionService` takes an optional `Reranker`; when one is given, reranking is the default.
- **Reranking on:**
  - `search(query, limit, rerank=None)` fetches `max(limit, 30)` candidates, reranks them and returns `limit`;
  - `ask` reranks 30 candidates, then applies the dense threshold, then keeps 3.
- **Reranking off:** the F-04a behaviour, unchanged.
- `FoundPassage` gains `rerank_score: float | None`.
- Asking for reranking when no reranker is configured raises `RerankerOff`.

### Settings, composition, API

- `ASSISTANT_RERANKER: Literal["on", "off"] = "on"`.
- `reranker_for(settings)` returns a checked `BgeReranker` or `None`. `Adapters` gains `reranker`.
- `SearchRequest.rerank: bool | None = None`, where `None` means the configured default.
- `SearchHit.rerank_score: float | None`.
- `RerankerOff` maps to 409 `reranker_off`.
- `make api-client` regenerates the TypeScript client.

### Evaluation

- Two Promptfoo providers, `reranked` and `hybrid`, send `rerank: true` and `rerank: false` to the same API and index. They run one request at a time (`-j 1`), so the latency is per request.
- The report keeps `metrics` and `missed` for the gated mode, which the gate reads as before. It adds:
  - `modes`, with each mode's metrics, missed cases and search latency (median and 95th percentile, in ms);
  - `out_of_scope_top_similarity`.

  Latency and that similarity are not gated.
- `GATED_MODE` in `run.py` is the API's default mode, and it changes with that default.

## Steps

### Step 1. Reranker port, ordering and fake

- Kind: code
- Tests first:
  - **`tests/unit/domain/test_rerank.py`:**
    - candidates come back by score, highest first;
    - equal scores keep the hybrid order;
    - the counts of scores and candidates must match.
  - **`tests/contract/test_reranker.py`** (fake now, real adapter in step 2):
    - one score per passage, in order;
    - a passage that answers the query scores above an unrelated one;
    - the same input gives the same scores.
- Change: `ports/reranker.py`, `domain/` (ordering), `adapters/fakes/reranker.py`.
- [x] red
- [x] green

### Step 2. Pinned BGE reranker and its adapter

- Kind: code
- Tests first:
  - **unit:**
    - `BGE_RERANKER` is in `PINNED_MODELS` at revision `953dc6f6…`;
    - `BgeReranker.ensure_ready` raises `ModelsNotReady` naming the model when a file is missing or wrong.
  - **contract (integration):** the step 1 contract, run against `BgeReranker`, plus a Polish query whose English answer scores above an unrelated English passage.
- Change: `adapters/pinned_models.py` (hashes taken from the downloaded files), `adapters/bge_reranker.py`. `make models` then fetches the model.
- [x] red
- [x] green

### Step 3. Reranking in the question service

- Kind: code
- Tests first, in `tests/unit/services/test_question_service.py`:
  - **With a reranker:**
    - search returns the reranker's order with `rerank_score`, from 30 candidates;
    - ask answers from the reranked best passage.
  - **Off by default or by request, or no reranker:** the order equals the index's, and `rerank_score` is `None`.
  - **Refusal:** an out-of-scope question is refused even when the reranker scores a passage high, because the dense threshold decides.
  - **No reranker:** asking for reranking raises `RerankerOff`.
- Change: `services/questions.py`, `domain/errors.py`.
- [x] red
- [x] green

### Step 4. Setting, composition and API

- Kind: code
- Tests first:
  - **Settings:** `reranker` defaults to `on` and accepts `off`.
  - **`reranker_for`:**
    - with `off`, it returns nothing and checks no files;
    - with `on` and a missing model, it raises `ModelsNotReady` naming the reranker.
  - **API:**
    - `rerank: false` returns the hybrid order with `rerank_score: null`;
    - `rerank: true` returns reranked hits with scores;
    - with no reranker, `rerank: true` is a 409 `reranker_off`;
    - the OpenAPI contract has the new fields.
- Change: `settings.py`, `app.py`, `api/schemas.py`, `api/routes/search.py`, `api/errors.py`, the generated client (`make api-client`), `.env.example`.
- [x] red
- [x] green

### Step 5. Evaluation of both modes

- Kind: eval (harness code with its tests)
- Tests first, in `evals/tests/`:
  - **Suite:** the Promptfoo suite has the providers `reranked` and `hybrid`, with `rerank` true and false.
  - **Promptfoo glue:**
    - `hits_by_case` groups hits by provider and case and returns each response's latency;
    - the command runs with one request at a time.
  - **Metrics:** latency median and 95th percentile; the highest similarity of the out-of-scope cases.
  - **Report:**
    - `modes` holds both modes;
    - `metrics` and `missed` are the gated mode's;
    - the Markdown shows both modes side by side.
  - **Gate:** it reads only the gated mode's metrics.
- Change: `evals/promptfoo/retrieval.yaml`, `evals/harness/{promptfoo,metrics,report,run}.py`.
- [x] red
- [x] green

### Step 5a. Half precision on MPS

- Kind: code (added after the first measurement, see "Changes during the build")
- Tests first:
  - **unit:** the reranker runs in float16 on MPS and in float32 on CPU;
  - **integration:**
    - on a machine with MPS, the loaded model is float16;
    - its scores stay within 0.01 of float32 on CPU for the same pairs.
- Change: `adapters/bge_reranker.py`.
- [x] red
- [x] green

### Step 6. Measure and record

- Kind: eval
- Run `make eval`, then apply spec decision 4:
  - **Reranker on by default** if recall@3 and MRR are higher with it, no metric is more than 5 points worse, and the p95 search latency is under 1 s.
  - **Otherwise off by default:** the default setting and `GATED_MODE` change, in their own red/green pair, because the tests pin the default.
- Commit:
  - the record `docs/evals/2026-10-29-retrieval-reranker.md`, with both modes, per-case changes, latency, the out-of-scope margin and the decision;
  - the new `retrieval-baseline.json`.
- If a criterion fails in a way the spec did not foresee, stop and bring the numbers to the human.
- [x] green

### Step 7. Documentation

- Kind: setup (one `docs` commit)
- Change:
  - **`architecture.md`:** the `Reranker` port row and the search flow;
  - **README:** status, the model in the licence table, the size of `make models`;
  - **`.env.example`**;
  - **backlog:** the follow-up item for the top out-of-scope similarity is done.
- [x] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 reranked order, ties by hybrid order, response says so | 1, 3, 4 |
| AC-2 off means exactly the hybrid order | 3, 4 |
| AC-3 missing model refused when on, ignored when off | 2, 4 |
| AC-4 out-of-scope still refused | 3, 6 |
| AC-5 both modes, latency and out-of-scope similarity in the report; gate on the default | 5, 6 |
| AC-6 result recorded, default follows it | 6 |

## Changes during the build

- **Half precision on MPS (step 5a).** The first `make eval` gave the following with the reranker:
  - recall@3 95.2 % (90.5 % without);
  - MRR 0.873 (0.821 without);
  - p95 search latency 1599 ms, above the 1 s limit of spec decision 4.

  Scoring 30 pairs took 785 ms in float32 and 353 ms in float16 on MPS, with scores equal to three decimals. The human approved trying float16 on MPS before deciding the default (2026-10-29). Decision 4 is unchanged.
- **`ref-annex-iii` stays outside the top 3 (review finding 4).** It ends at rank 6 with the reranker. The human accepted the miss on 2026-10-29, and the case moves to F-09.
- **Review fixes.**
  - Answers use the reranker's top 10.
  - The reranker loads at startup.
  - `make eval` adds answerable@3, a warm-up search per mode and the reranker's settings.

  The measurement after them is the baseline.
