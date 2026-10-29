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


def first_rank(result: CaseResult) -> int | None:
    raise NotImplementedError


def compute(results: Sequence[CaseResult], threshold: float) -> Metrics:
    raise NotImplementedError
