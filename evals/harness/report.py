"""Run reports in JSON and Markdown (AI-61)."""

from collections.abc import Mapping
from typing import Any

from harness.metrics import Metrics

REQUIRED_METADATA = (
    "started_at",
    "git_commit",
    "dataset",
    "models",
    "qdrant_version",
    "settings",
    "hardware",
)


def build_report(metrics: Metrics, metadata: Mapping[str, Any], threshold: float) -> dict[str, Any]:
    """Everything needed to compare and reproduce a run; fails if metadata is incomplete."""
    missing = [name for name in REQUIRED_METADATA if name not in metadata]
    if missing:
        raise ValueError(f"run metadata lacks {', '.join(missing)}")
    return {
        "metrics": {
            name: {"value": metric.value, "cases": metric.cases}
            for name, metric in metrics.by_name.items()
        },
        "missed": dict(metrics.missed),
        "threshold": threshold,
        "metadata": dict(metadata),
    }


def markdown(report: Mapping[str, Any]) -> str:
    """A table of the metrics, the missed cases and the run metadata."""
    lines = ["| Metric | Value | Cases |", "|---|---|---|"]
    for name, metric in report["metrics"].items():
        lines.append(f"| {name} | {_format(name, metric['value'])} | {metric['cases']} |")
    lines += ["", f"Similarity threshold: {report['threshold']}", "", "Missed cases:", ""]
    lines += [f"- {case}: {reason}" for case, reason in report["missed"].items()] or ["- none"]
    lines += ["", "Run:", ""]
    lines += [f"- {name}: {value}" for name, value in report["metadata"].items()]
    return "\n".join(lines) + "\n"


def _format(name: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    # MRR is a mean of reciprocal ranks, not a share.
    return f"{value:.3f}" if name == "mrr" else f"{value * 100:.1f} %"
