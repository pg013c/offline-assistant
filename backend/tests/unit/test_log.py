import json
from collections.abc import Iterator

import pytest
import structlog

from assistant.app import main
from assistant.log import configure_logging
from assistant.settings import SettingsError


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


def test_app_factory_configures_logging_before_reading_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASSISTANT_DATA_DIR", raising=False)
    # main() sets these; recording them here restores them after the test.
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")

    with pytest.raises(SettingsError):
        main()

    assert structlog.is_configured()
