from pathlib import Path

import pytest

from assistant.app import main
from assistant.settings import SettingsError, load_settings, variable_name


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSISTANT_DATA_DIR", raising=False)


def test_missing_data_dir_fails_with_the_variable_name() -> None:
    with pytest.raises(SettingsError, match="ASSISTANT_DATA_DIR"):
        load_settings()


def test_data_dir_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))

    settings = load_settings()

    assert settings.data_dir == tmp_path


def test_unknown_assistant_variables_are_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_NOT_A_SETTING", "1")

    settings = load_settings()

    assert settings.data_dir == tmp_path


def test_app_factory_fails_at_startup_without_required_settings() -> None:
    with pytest.raises(SettingsError, match="ASSISTANT_DATA_DIR"):
        main()


def test_app_factory_builds_the_app_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))

    app = main()

    assert app.state.settings.data_dir == tmp_path


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        (("data_dir",), "ASSISTANT_DATA_DIR"),
        (("models", "default"), "ASSISTANT_MODELS_DEFAULT"),
        ((), "ASSISTANT_* settings"),
    ],
)
def test_validation_error_locations_name_the_environment_variable(
    location: tuple[str, ...], expected: str
) -> None:
    assert variable_name(location) == expected
