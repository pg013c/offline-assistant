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
