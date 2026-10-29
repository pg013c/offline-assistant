import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from assistant.app import main
from assistant.log import configure_logging


@pytest.fixture(autouse=True)
def reset_structlog() -> Iterator[None]:
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()


def test_events_are_written_as_json_with_level_timestamp_and_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()

    structlog.get_logger("test").info("document_ingested", document_id="d-1")

    event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert event["event"] == "document_ingested"
    assert event["level"] == "info"
    assert event["document_id"] == "d-1"
    assert "timestamp" in event


def test_events_below_the_configured_level_are_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="info")

    structlog.get_logger("test").debug("noise")

    assert capsys.readouterr().out == ""


def test_app_factory_configures_logging(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_DOCUMENT_PARSER", "text-only")

    main()

    assert structlog.is_configured()
