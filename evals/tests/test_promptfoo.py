import json

from harness.metrics import Hit
from harness.promptfoo import environment, hits_by_case


def test_promptfoo_runs_without_telemetry_updates_or_sharing() -> None:
    env = environment({"PATH": "/usr/bin"}, api_url="http://127.0.0.1:8021")

    assert env["PROMPTFOO_DISABLE_TELEMETRY"] == "1"
    assert env["PROMPTFOO_DISABLE_UPDATE"] == "1"
    assert env["PROMPTFOO_DISABLE_SHARING"] == "1"
    assert env["EVAL_API_URL"] == "http://127.0.0.1:8021"
    assert env["PATH"] == "/usr/bin"


def test_hits_are_read_per_case_from_promptfoo_results() -> None:
    passages = [
        {"chunk_id": "d:2", "similarity": 0.8},
        {"chunk_id": "d:5", "similarity": 0.4},
    ]
    results = {
        "results": {
            "results": [
                {
                    "vars": {"case_id": "a", "question": "?"},
                    "response": {"output": json.dumps(passages)},
                },
                {"vars": {"case_id": "b", "question": "?"}, "response": {"output": "[]"}},
            ]
        }
    }

    assert hits_by_case(results) == {
        "a": (Hit("d:2", 0.8), Hit("d:5", 0.4)),
        "b": (),
    }
