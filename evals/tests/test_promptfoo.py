import json
from pathlib import Path

import pytest
import yaml

from harness.metrics import Hit
from harness.promptfoo import (
    MODES,
    PromptfooError,
    Response,
    command_line,
    environment,
    responses_by_mode,
)


def test_promptfoo_runs_without_telemetry_updates_or_sharing() -> None:
    env = environment({"PATH": "/usr/bin"}, api_url="http://127.0.0.1:8021")

    assert env["PROMPTFOO_DISABLE_TELEMETRY"] == "1"
    assert env["PROMPTFOO_DISABLE_UPDATE"] == "1"
    assert env["PROMPTFOO_DISABLE_SHARING"] == "1"
    assert env["EVAL_API_URL"] == "http://127.0.0.1:8021"
    assert env["PATH"] == "/usr/bin"


def entry(
    mode: str, case_id: str, passages: list[dict[str, object]], latency: int
) -> dict[str, object]:
    return {
        "provider": {"id": "https", "label": mode},
        "vars": {"case_id": case_id, "question": "?"},
        "response": {"output": json.dumps(passages)},
        "latencyMs": latency,
    }


def test_responses_are_read_per_mode_and_case_with_their_latency() -> None:
    passages = [
        {"chunk_id": "d:2", "similarity": 0.8},
        {"chunk_id": "d:5", "similarity": 0.4},
    ]
    results = {
        "results": {
            "results": [
                entry("reranked", "a", passages, 120),
                entry("hybrid", "a", passages[::-1], 40),
                entry("reranked", "b", [], 90),
                entry("hybrid", "b", [], 30),
            ]
        }
    }

    assert responses_by_mode(results) == {
        "reranked": {
            "a": Response((Hit("d:2", 0.8), Hit("d:5", 0.4)), 120.0),
            "b": Response((), 90.0),
        },
        "hybrid": {
            "a": Response((Hit("d:5", 0.4), Hit("d:2", 0.8)), 40.0),
            "b": Response((), 30.0),
        },
    }


def test_a_case_without_output_is_reported_by_id() -> None:
    results = {
        "results": {
            "results": [
                {
                    "provider": {"label": "reranked"},
                    "vars": {"case_id": "broken"},
                    "response": {"error": "connection refused"},
                },
            ]
        }
    }

    with pytest.raises(PromptfooError, match=r"broken.*connection refused"):
        responses_by_mode(results)


def test_promptfoo_keeps_results_in_the_runs_files_only(tmp_path: Path) -> None:
    command = command_line(Path("pnpm"), Path("suite.yaml"), Path("tests.yaml"), Path("out.json"))

    assert {"--no-write", "--no-share", "--no-cache"} <= set(command)
    assert command[command.index("--output") + 1] == "out.json"


def test_requests_run_one_at_a_time_so_latency_is_per_request() -> None:
    command = command_line(Path("pnpm"), Path("suite.yaml"), Path("tests.yaml"), Path("out.json"))

    assert command[command.index("--max-concurrency") + 1] == "1"


def test_the_suite_searches_with_and_without_the_reranker() -> None:
    suite = yaml.safe_load(
        (Path(__file__).parents[1] / "promptfoo" / "retrieval.yaml").read_text(encoding="utf-8")
    )

    modes = {
        provider["label"]: provider["config"]["body"]["rerank"] for provider in suite["providers"]
    }
    assert modes == {"reranked": True, "hybrid": False}
    assert set(MODES) == set(modes)
