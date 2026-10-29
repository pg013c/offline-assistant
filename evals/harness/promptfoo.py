"""Running Promptfoo and reading its results (ADR 0018)."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
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


EVALS_PROJECT = Path(__file__).parents[1]
# Provider labels in the suite: search with the reranker and without it (F-05).
MODES = ("reranked", "hybrid")


@dataclass(frozen=True)
class Response:
    hits: tuple[Hit, ...]
    latency_ms: float


def command_line(pnpm: Path, suite: Path, tests: Path, output: Path) -> list[str]:
    """The Promptfoo command of a run; results go to `output` and nowhere else: not to
    Promptfoo's database in the home directory, not to a share link, not to a cache."""
    return [
        str(pnpm),
        "--dir",
        str(EVALS_PROJECT),
        "exec",
        "promptfoo",
        "eval",
        "--config",
        str(suite),
        "--tests",
        str(tests),
        "--output",
        str(output),
        "--no-write",
        "--no-share",
        "--no-cache",
        "--no-progress-bar",
        # One request at a time, so each latency is that of a search alone.
        "--max-concurrency",
        "1",
    ]


def environment(base: Mapping[str, str], api_url: str) -> dict[str, str]:
    """The environment Promptfoo runs with: the caller's, offline, with the API to call."""
    return {**base, **OFFLINE, "EVAL_API_URL": api_url}


def responses_by_mode(results: Mapping[str, Any]) -> dict[str, dict[str, Response]]:
    """Ranked hits and latency per mode and case id, from Promptfoo's JSON output."""
    found: dict[str, dict[str, Response]] = {}
    for entry in results["results"]["results"]:
        mode = entry["provider"]["label"]
        case_id = entry["vars"]["case_id"]
        response = entry.get("response") or {}
        if "output" not in response:
            reason = response.get("error") or entry.get("error") or "no output"
            raise PromptfooError(f"{case_id} ({mode}): Promptfoo got no result ({reason})")
        passages = json.loads(response["output"])
        hits = tuple(
            Hit(chunk_id=passage["chunk_id"], similarity=float(passage["similarity"]))
            for passage in passages
        )
        found.setdefault(mode, {})[case_id] = Response(hits, float(entry["latencyMs"]))
    return found
