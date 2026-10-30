import json
from pathlib import Path

import pytest

from assistant.openapi import openapi_json


def test_the_schema_is_exported_without_parsing_models(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # `make` exports ASSISTANT_MODELS_DIR; CI jobs that only check the API have no models.
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "no-models"))
    monkeypatch.delenv("ASSISTANT_DOCUMENT_PARSER", raising=False)

    schema = json.loads(openapi_json())

    assert "/api/documents" in schema["paths"]


def test_searches_can_choose_reranking_and_hits_carry_its_score() -> None:
    schemas = json.loads(openapi_json())["components"]["schemas"]

    assert "rerank" in schemas["SearchRequest"]["properties"]
    assert "rerank" not in schemas["SearchRequest"].get("required", [])
    assert "rerank_score" in schemas["SearchHit"]["properties"]


def test_the_chat_stream_documents_discard_and_error_events_and_usage() -> None:
    schemas = json.loads(openapi_json())["components"]["schemas"]

    assert {"ChatDiscardEvent", "ChatErrorEvent", "ChatUsage"} <= set(schemas)
    assert schemas["ChatErrorEvent"]["properties"]["code"]["enum"] == [
        "invalid_answer",
        "model_unreachable",
        "model_timeout",
        "model_error",
        "too_many_tool_turns",
    ]
    assert "usage" in schemas["ChatEndEvent"]["properties"]


def test_the_chat_stream_documents_tool_events_and_tool_turns() -> None:
    schemas = json.loads(openapi_json())["components"]["schemas"]

    tool = schemas["ChatToolEvent"]
    assert set(tool["required"]) == {"type", "name", "arguments"}
    assert "tool_turns" in schemas["ChatUsage"]["required"]
