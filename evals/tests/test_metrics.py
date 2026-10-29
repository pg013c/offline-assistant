import pytest

from harness.metrics import (
    CaseResult,
    Hit,
    Latency,
    compute,
    first_rank,
    latency,
    top_out_of_scope_similarity,
)


def result(
    case_id: str, expected: set[str], hits: list[tuple[str, float]], behaviour: str = "answer"
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        behaviour=behaviour,
        expected_chunk_ids=frozenset(expected),
        hits=tuple(Hit(chunk_id=chunk, similarity=similarity) for chunk, similarity in hits),
    )


def test_the_rank_is_the_position_of_the_first_expected_chunk() -> None:
    found = result("a", {"d:7", "d:9"}, [("d:1", 0.9), ("d:9", 0.8), ("d:7", 0.7)])

    assert first_rank(found) == 2


def test_a_case_without_an_expected_chunk_in_the_hits_has_no_rank() -> None:
    assert first_rank(result("a", {"d:7"}, [("d:1", 0.9)])) is None


def test_recall_and_mrr_count_in_scope_cases_only() -> None:
    results = [
        result("first", {"d:1"}, [("d:1", 0.8)]),
        result("third", {"d:3"}, [("d:1", 0.7), ("d:2", 0.7), ("d:3", 0.6)]),
        result("fifth", {"d:5"}, [(f"d:{n}", 0.6) for n in range(1, 6)]),
        result("missed", {"d:9"}, [("d:1", 0.6)]),
        result("oos", set(), [("d:1", 0.3)], behaviour="refuse"),
    ]

    metrics = compute(results, threshold=0.5)

    assert metrics["recall@3"].value == pytest.approx(2 / 4)
    assert metrics["recall@3"].cases == 4
    assert metrics["recall@10"].value == pytest.approx(3 / 4)
    assert metrics["mrr"].value == pytest.approx((1 + 1 / 3 + 1 / 5 + 0) / 4)


def test_refusal_shares_use_the_threshold_on_the_best_hit() -> None:
    results = [
        result("oos-quiet", set(), [("d:1", 0.3)], behaviour="refuse"),
        result("oos-noisy", set(), [("d:1", 0.6)], behaviour="refuse"),
        result("oos-empty", set(), [], behaviour="refuse"),
        result("found", {"d:1"}, [("d:1", 0.7)]),
        result("too-weak", {"d:2"}, [("d:2", 0.4)]),
    ]

    metrics = compute(results, threshold=0.5)

    assert metrics["out_of_scope_refused"].value == pytest.approx(2 / 3)
    assert metrics["out_of_scope_refused"].cases == 3
    assert metrics["in_scope_unanswered"].value == pytest.approx(1 / 2)
    assert metrics["in_scope_unanswered"].cases == 2


def test_missed_cases_are_listed_with_their_reason() -> None:
    results = [
        result("ok", {"d:1"}, [("d:1", 0.8)]),
        result("deep", {"d:5"}, [(f"d:{n}", 0.6) for n in range(1, 6)]),
        result("oos-noisy", set(), [("d:1", 0.6)], behaviour="refuse"),
    ]

    metrics = compute(results, threshold=0.5)

    assert metrics.missed == {
        "deep": "first expected chunk at rank 5",
        "oos-noisy": "best hit 0.60 reaches the threshold 0.50",
    }


def test_an_empty_group_has_no_value() -> None:
    metrics = compute([result("found", {"d:1"}, [("d:1", 0.7)])], threshold=0.5)

    assert metrics["out_of_scope_refused"].value is None
    assert metrics["out_of_scope_refused"].cases == 0


def test_in_scope_cases_below_the_threshold_are_listed_as_missed() -> None:
    results = [result("weak-but-first", {"d:1"}, [("d:1", 0.4)])]

    metrics = compute(results, threshold=0.5)

    assert metrics.missed == {"weak-but-first": "best hit 0.40 is below the threshold 0.50"}


def test_latency_has_a_median_and_a_95th_percentile() -> None:
    values = [float(n) for n in range(10, 210, 10)]  # 10 .. 200, 20 values

    assert latency(values) == Latency(median_ms=105.0, p95_ms=190.0)


def test_latency_of_no_requests_is_unknown() -> None:
    assert latency([]) == Latency(median_ms=None, p95_ms=None)


def test_the_top_out_of_scope_similarity_is_the_best_hit_of_any_refuse_case() -> None:
    results = [
        CaseResult("in", "answer", frozenset({"d:1"}), (Hit("d:1", 0.9),)),
        CaseResult("oos-a", "refuse", frozenset(), (Hit("d:2", 0.31), Hit("d:3", 0.12))),
        CaseResult("oos-b", "refuse", frozenset(), (Hit("d:4", 0.38),)),
        CaseResult("oos-c", "refuse", frozenset(), ()),
    ]

    assert top_out_of_scope_similarity(results) == 0.38


def test_without_out_of_scope_hits_the_top_similarity_is_unknown() -> None:
    assert top_out_of_scope_similarity([]) is None
