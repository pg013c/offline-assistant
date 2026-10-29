import pytest

from assistant.domain.ranking import rerank


def test_candidates_come_back_by_score_highest_first() -> None:
    assert rerank(["a", "b", "c"], [0.1, 0.9, 0.5]) == [("b", 0.9), ("c", 0.5), ("a", 0.1)]


def test_equal_scores_keep_the_order_the_candidates_came_in() -> None:
    assert rerank(["a", "b", "c", "d"], [0.2, 0.7, 0.2, 0.7]) == [
        ("b", 0.7),
        ("d", 0.7),
        ("a", 0.2),
        ("c", 0.2),
    ]


def test_no_candidates_give_nothing() -> None:
    assert rerank([], []) == []


def test_every_candidate_needs_one_score() -> None:
    with pytest.raises(ValueError, match="2 candidates, 1 scores"):
        rerank(["a", "b"], [0.5])
