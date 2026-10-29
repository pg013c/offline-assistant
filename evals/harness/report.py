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
    raise NotImplementedError


def markdown(report: Mapping[str, Any]) -> str:
    raise NotImplementedError
