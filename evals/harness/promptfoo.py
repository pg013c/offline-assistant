"""Running Promptfoo and reading its results (ADR 0018)."""

from collections.abc import Mapping
from typing import Any

from harness.metrics import Hit


def environment(base: Mapping[str, str], api_url: str) -> dict[str, str]:
    raise NotImplementedError


def hits_by_case(results: Mapping[str, Any]) -> dict[str, tuple[Hit, ...]]:
    raise NotImplementedError
