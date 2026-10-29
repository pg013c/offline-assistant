from harness.metrics import Metric, Metrics
from harness.report import REQUIRED_METADATA, build_report, markdown

METRICS = Metrics(
    by_name={
        "recall@3": Metric(0.75, 20),
        "recall@10": Metric(0.9, 20),
        "mrr": Metric(0.6123, 20),
        "out_of_scope_refused": Metric(1.0, 3),
        "in_scope_unanswered": Metric(None, 0),
    },
    missed={"en-gdpr-dpo": "first expected chunk at rank 5"},
)
METADATA = {name: f"<{name}>" for name in REQUIRED_METADATA}


def test_the_report_keeps_metrics_with_counts_missed_cases_and_metadata() -> None:
    report = build_report(METRICS, METADATA, threshold=0.5, expected={})

    assert report["metrics"]["recall@3"] == {"value": 0.75, "cases": 20}
    assert report["metrics"]["in_scope_unanswered"] == {"value": None, "cases": 0}
    assert report["missed"] == {"en-gdpr-dpo": "first expected chunk at rank 5"}
    assert report["threshold"] == 0.5
    assert {"models", "dataset", "hardware", "git_commit"} <= set(report["metadata"])


def test_the_markdown_table_lists_every_metric() -> None:
    text = markdown(build_report(METRICS, METADATA, threshold=0.5, expected={}))

    assert "| recall@3 | 75.0 % | 20 |" in text
    assert "| mrr | 0.612 | 20 |" in text
    assert "| in_scope_unanswered | n/a | 0 |" in text
    assert "en-gdpr-dpo: first expected chunk at rank 5" in text


def test_the_report_records_the_resolved_expected_chunks() -> None:
    expected = {"case-b": frozenset({"d:3", "d:1"}), "oos": frozenset()}

    report = build_report(METRICS, METADATA, threshold=0.5, expected=expected)

    assert report["expected"] == {"case-b": ["d:1", "d:3"], "oos": []}
