"""Retrieval metrics from ranked hits and expected chunks (F-04)."""

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    similarity: float


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    behaviour: str
    expected_chunk_ids: frozenset[str]
    hits: tuple[Hit, ...]


@dataclass(frozen=True)
class Metric:
    value: float | None
    cases: int


@dataclass(frozen=True)
class Metrics:
    by_name: dict[str, Metric]
    # Case id -> why it missed.
    missed: dict[str, str] = field(default_factory=dict)

    def __getitem__(self, name: str) -> Metric:
        return self.by_name[name]


RECALL_AT = (3, 10)
# A found passage counts as missed below this rank (the answer uses three passages).
CITED_PASSAGES = 3


def first_rank(result: CaseResult) -> int | None:
    """1-based rank of the first hit that is an expected chunk, or None."""
    for rank, hit in enumerate(result.hits, start=1):
        if hit.chunk_id in result.expected_chunk_ids:
            return rank
    return None


def compute(results: Sequence[CaseResult], threshold: float) -> Metrics:
    """Recall@k and MRR over in-scope cases; refusal shares at the similarity threshold.

    A case is "refused" when its best hit is below the threshold: the answer would then cite
    nothing.
    """
    in_scope = [result for result in results if result.behaviour == "answer"]
    out_of_scope = [result for result in results if result.behaviour == "refuse"]
    ranks = {result.case_id: first_rank(result) for result in in_scope}

    def refused(result: CaseResult) -> bool:
        return not result.hits or max(hit.similarity for hit in result.hits) < threshold

    by_name = {
        f"recall@{k}": _share(
            sum(1 for rank in ranks.values() if rank is not None and rank <= k), len(in_scope)
        )
        for k in RECALL_AT
    }
    by_name["mrr"] = Metric(
        value=(
            sum(1 / rank for rank in ranks.values() if rank is not None) / len(in_scope)
            if in_scope
            else None
        ),
        cases=len(in_scope),
    )
    by_name["out_of_scope_refused"] = _share(
        sum(1 for result in out_of_scope if refused(result)), len(out_of_scope)
    )
    by_name["in_scope_unanswered"] = _share(
        sum(1 for result in in_scope if refused(result)), len(in_scope)
    )

    missed: dict[str, str] = {}
    for case_id, rank in ranks.items():
        if rank is None:
            missed[case_id] = "no expected chunk among the hits"
        elif rank > CITED_PASSAGES:
            missed[case_id] = f"first expected chunk at rank {rank}"
    for result in out_of_scope:
        if not refused(result):
            best = max(hit.similarity for hit in result.hits)
            missed[result.case_id] = f"best hit {best:.2f} reaches the threshold {threshold:.2f}"
    return Metrics(by_name=by_name, missed=missed)


def _share(count: int, total: int) -> Metric:
    return Metric(value=count / total if total else None, cases=total)
