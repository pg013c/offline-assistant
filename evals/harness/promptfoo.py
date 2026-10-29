"""Running Promptfoo and reading its results (ADR 0018)."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from harness.metrics import Hit

# Promptfoo sends nothing anywhere: no usage data, no update checks, no shared results.
OFFLINE = {
    "PROMPTFOO_DISABLE_TELEMETRY": "1",
    "PROMPTFOO_DISABLE_UPDATE": "1",
    "PROMPTFOO_DISABLE_SHARING": "1",
}


class PromptfooError(Exception):
    """Promptfoo returned no output for a case; the message names it."""


def command_line(pnpm: Path, suite: Path, tests: Path, output: Path) -> list[str]:
    """The Promptfoo command of a run; results go to `output` and nowhere else."""
    raise NotImplementedError


def environment(base: Mapping[str, str], api_url: str) -> dict[str, str]:
    """The environment Promptfoo runs with: the caller's, offline, with the API to call."""
    return {**base, **OFFLINE, "EVAL_API_URL": api_url}


def hits_by_case(results: Mapping[str, Any]) -> dict[str, tuple[Hit, ...]]:
    """Ranked hits per case id, from Promptfoo's JSON output."""
    found: dict[str, tuple[Hit, ...]] = {}
    for entry in results["results"]["results"]:
        case_id = entry["vars"]["case_id"]
        response = entry.get("response") or {}
        if "output" not in response:
            reason = response.get("error") or entry.get("error") or "no output"
            raise PromptfooError(f"{case_id}: Promptfoo got no result ({reason})")
        passages = json.loads(response["output"])
        found[case_id] = tuple(
            Hit(chunk_id=passage["chunk_id"], similarity=float(passage["similarity"]))
            for passage in passages
        )
    return found
