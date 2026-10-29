from harness.gate import check


def test_a_drop_of_more_than_5_points_fails_and_names_the_metric() -> None:
    failures = check(
        current={"recall@3": 0.70, "mrr": 0.60}, baseline={"recall@3": 0.80, "mrr": 0.62}
    )

    assert failures == ["recall@3 dropped from 80.0 to 70.0 (more than 5 points)"]


def test_a_drop_of_at_most_5_points_passes() -> None:
    assert check(current={"recall@3": 0.75}, baseline={"recall@3": 0.80}) == []


def test_for_unanswered_in_scope_questions_a_rise_is_the_regression() -> None:
    failures = check(current={"in_scope_unanswered": 0.20}, baseline={"in_scope_unanswered": 0.10})

    assert failures == ["in_scope_unanswered rose from 10.0 to 20.0 (more than 5 points)"]


def test_metrics_without_a_value_or_without_a_baseline_are_skipped() -> None:
    assert check(current={"recall@3": None, "mrr": 0.1}, baseline={"recall@3": 0.9}) == []
