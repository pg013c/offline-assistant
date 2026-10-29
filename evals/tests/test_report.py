from harness.metrics import Latency, Metric, Metrics
from harness.report import REQUIRED_METADATA, ModeResult, build_report, markdown

RERANKED = ModeResult(
    metrics=Metrics(
        by_name={
            "recall@3": Metric(0.75, 20),
            "recall@10": Metric(0.9, 20),
            "mrr": Metric(0.6123, 20),
            "out_of_scope_refused": Metric(1.0, 3),
            "in_scope_unanswered": Metric(None, 0),
        },
        missed={"en-gdpr-dpo": "first expected chunk at rank 5"},
    ),
    latency=Latency(median_ms=180.0, p95_ms=420.0),
    out_of_scope_top_similarity=0.38,
)
HYBRID = ModeResult(
    metrics=Metrics(
        by_name={
            "recall@3": Metric(0.6, 20),
            "recall@10": Metric(0.9, 20),
            "mrr": Metric(0.5, 20),
            "out_of_scope_refused": Metric(1.0, 3),
            "in_scope_unanswered": Metric(None, 0),
        },
        missed={"ref-annex-iii": "first expected chunk at rank 9"},
    ),
    latency=Latency(median_ms=60.0, p95_ms=95.0),
    out_of_scope_top_similarity=0.35,
)
MODES = {"reranked": RERANKED, "hybrid": HYBRID}
METADATA = {name: f"<{name}>" for name in REQUIRED_METADATA}


def test_the_gated_modes_metrics_and_missed_cases_are_the_reports() -> None:
    built = build_report(MODES, "reranked", METADATA, threshold=0.5, expected={})

    assert built["gated_mode"] == "reranked"
    assert built["metrics"]["recall@3"] == {"value": 0.75, "cases": 20}
    assert built["metrics"]["in_scope_unanswered"] == {"value": None, "cases": 0}
    assert built["missed"] == {"en-gdpr-dpo": "first expected chunk at rank 5"}
    assert built["threshold"] == 0.5
    assert {"models", "dataset", "hardware", "git_commit"} <= set(built["metadata"])


def test_every_mode_keeps_its_metrics_missed_cases_latency_and_out_of_scope_margin() -> None:
    built = build_report(MODES, "hybrid", METADATA, threshold=0.5, expected={})

    assert built["metrics"]["recall@3"] == {"value": 0.6, "cases": 20}
    assert built["modes"]["reranked"]["metrics"]["mrr"] == {"value": 0.6123, "cases": 20}
    assert built["modes"]["hybrid"]["missed"] == {"ref-annex-iii": "first expected chunk at rank 9"}
    assert built["modes"]["reranked"]["latency_ms"] == {"median": 180.0, "p95": 420.0}
    assert built["modes"]["hybrid"]["out_of_scope_top_similarity"] == 0.35


def test_the_markdown_compares_the_modes_side_by_side() -> None:
    text = markdown(build_report(MODES, "reranked", METADATA, threshold=0.5, expected={}))

    assert text.startswith("| Metric | reranked | hybrid | Cases |")
    assert "| recall@3 | 75.0 % | 60.0 % | 20 |" in text
    assert "| mrr | 0.612 | 0.500 | 20 |" in text
    assert "| in_scope_unanswered | n/a | n/a | 0 |" in text
    assert "| search latency, median | 180 ms | 60 ms | |" in text
    assert "| search latency, 95th percentile | 420 ms | 95 ms | |" in text
    assert "| top out-of-scope similarity | 0.38 | 0.35 | |" in text
    assert "Gated mode: reranked" in text
    assert "en-gdpr-dpo: first expected chunk at rank 5" in text
    assert "ref-annex-iii: first expected chunk at rank 9" in text


def test_the_report_records_the_resolved_expected_chunks() -> None:
    expected = {"case-b": frozenset({"d:3", "d:1"}), "oos": frozenset()}

    built = build_report(MODES, "reranked", METADATA, threshold=0.5, expected=expected)

    assert built["expected"] == {"case-b": ["d:1", "d:3"], "oos": []}
