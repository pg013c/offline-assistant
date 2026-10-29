"""Run reports in JSON and Markdown (AI-61)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from harness.metrics import Latency, Metrics

REQUIRED_METADATA = (
    "started_at",
    "git_commit",
    "dataset",
    "models",
    "qdrant_version",
    "settings",
    "hardware",
)


@dataclass(frozen=True)
class ModeResult:
    metrics: Metrics
    latency: Latency
    out_of_scope_top_similarity: float | None
    # The first, unmeasured request of the mode.
    warm_up_ms: float | None = None


def build_report(
    modes: Mapping[str, ModeResult],
    gated_mode: str,
    metadata: Mapping[str, Any],
    threshold: float,
    expected: Mapping[str, frozenset[str]],
) -> dict[str, Any]:
    """Everything needed to compare and reproduce a run; fails if metadata is incomplete.

    `metrics` and `missed` are the gated mode's; `modes` holds every mode's results.
    """
    missing = [name for name in REQUIRED_METADATA if name not in metadata]
    if missing:
        raise ValueError(f"run metadata lacks {', '.join(missing)}")
    by_mode = {
        mode: {
            "metrics": {
                name: {"value": metric.value, "cases": metric.cases}
                for name, metric in result.metrics.by_name.items()
            },
            "missed": dict(result.metrics.missed),
            "latency_ms": {"median": result.latency.median_ms, "p95": result.latency.p95_ms},
            "out_of_scope_top_similarity": result.out_of_scope_top_similarity,
            "warm_up_ms": result.warm_up_ms,
        }
        for mode, result in modes.items()
    }
    return {
        "gated_mode": gated_mode,
        "metrics": by_mode[gated_mode]["metrics"],
        "missed": by_mode[gated_mode]["missed"],
        "modes": by_mode,
        # What each case was scored against, so a change in resolution shows up.
        "expected": {case: sorted(ids) for case, ids in expected.items()},
        "threshold": threshold,
        "metadata": dict(metadata),
    }


def markdown(report: Mapping[str, Any]) -> str:
    """The modes side by side, their missed cases and the run metadata."""
    modes: Mapping[str, Any] = report["modes"]
    names = list(modes)
    lines = [
        "| Metric | " + " | ".join(names) + " | Cases |",
        "|---|" + "---|" * len(names) + "---|",
    ]
    for name, metric in report["metrics"].items():
        values = [_format(name, modes[mode]["metrics"][name]["value"]) for mode in names]
        lines.append(f"| {name} | " + " | ".join(values) + f" | {metric['cases']} |")
    for label, key in (("median", "median"), ("95th percentile", "p95")):
        values = [_milliseconds(modes[mode]["latency_ms"][key]) for mode in names]
        lines.append(f"| search latency, {label} | " + " | ".join(values) + " | |")
    warm_ups = [_milliseconds(modes[mode].get("warm_up_ms")) for mode in names]
    lines.append("| warm-up request | " + " | ".join(warm_ups) + " | |")
    margins = [_similarity(modes[mode]["out_of_scope_top_similarity"]) for mode in names]
    lines.append("| top out-of-scope similarity | " + " | ".join(margins) + " | |")
    lines += [
        "",
        f"Gated mode: {report['gated_mode']}",
        "",
        f"Similarity threshold: {report['threshold']}",
    ]
    for mode in names:
        lines += ["", f"Missed cases ({mode}):", ""]
        missed = modes[mode]["missed"].items()
        lines += [f"- {case}: {reason}" for case, reason in missed] or ["- none"]
    lines += ["", "Run:", ""]
    lines += [f"- {name}: {value}" for name, value in report["metadata"].items()]
    return "\n".join(lines) + "\n"


def _format(name: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    # MRR is a mean of reciprocal ranks, not a share.
    return f"{value:.3f}" if name == "mrr" else f"{value * 100:.1f} %"


def _milliseconds(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f} ms"


def _similarity(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"
