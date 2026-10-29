import os
from pathlib import Path

import pytest

from assistant.adapters.pinned_models import ModelsNotReady
from assistant.app import main, reranker_for
from assistant.settings import Settings, SettingsError, load_settings, variable_name


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ASSISTANT_DATA_DIR",
        "ASSISTANT_MODELS_DIR",
        "ASSISTANT_DOCUMENT_PARSER",
        "ASSISTANT_QDRANT_URL",
        "ASSISTANT_QDRANT_COLLECTION_PREFIX",
        "ASSISTANT_MIN_SIMILARITY",
        "ASSISTANT_RERANKER",
    ):
        monkeypatch.delenv(name, raising=False)
    # main() sets these; recording them here restores them after each test.
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")


def test_missing_data_dir_fails_with_the_variable_name() -> None:
    with pytest.raises(SettingsError, match="ASSISTANT_DATA_DIR"):
        load_settings()


def test_data_dir_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))

    settings = load_settings()

    assert settings.data_dir == tmp_path


def test_unknown_assistant_variables_are_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("ASSISTANT_NOT_A_SETTING", "1")

    settings = load_settings()

    assert settings.data_dir == tmp_path


def test_app_factory_fails_at_startup_without_required_settings() -> None:
    with pytest.raises(SettingsError, match="ASSISTANT_DATA_DIR"):
        main()


def test_search_settings_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("ASSISTANT_QDRANT_URL", "http://qdrant.internal:6333")
    monkeypatch.setenv("ASSISTANT_QDRANT_COLLECTION_PREFIX", "e2e")
    monkeypatch.setenv("ASSISTANT_MIN_SIMILARITY", "0.42")

    settings = load_settings()

    assert settings.qdrant_url == "http://qdrant.internal:6333"
    assert settings.qdrant_collection_prefix == "e2e"
    assert settings.min_similarity == 0.42


def test_search_settings_have_local_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))

    settings = load_settings()

    assert settings.qdrant_url == "http://127.0.0.1:6333"
    assert settings.qdrant_collection_prefix == "assistant"
    assert settings.min_similarity == 0.5


def test_the_models_directory_is_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_DOCUMENT_PARSER", "text-only")

    with pytest.raises(SettingsError, match="ASSISTANT_MODELS_DIR"):
        load_settings()


def test_startup_fails_when_the_embedding_model_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("ASSISTANT_DOCUMENT_PARSER", "text-only")

    with pytest.raises(ModelsNotReady, match=r"BAAI/bge-m3.*make models"):
        main()


def test_the_docling_parser_is_the_default_and_needs_a_models_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))

    with pytest.raises(SettingsError, match="ASSISTANT_MODELS_DIR"):
        load_settings()


def test_startup_fails_when_parsing_models_are_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))

    with pytest.raises(ModelsNotReady, match="make models"):
        main()


def test_the_app_forbids_model_downloads_before_loading_anything() -> None:
    with pytest.raises(SettingsError):
        main()

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


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


@pytest.mark.parametrize("value", ["-0.1", "1.5"])
def test_the_minimum_similarity_must_lie_between_0_and_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("ASSISTANT_MIN_SIMILARITY", value)

    with pytest.raises(SettingsError, match="ASSISTANT_MIN_SIMILARITY"):
        load_settings()


def test_reranking_is_on_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))

    assert load_settings().reranker == "on"


def test_reranking_can_be_switched_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("ASSISTANT_RERANKER", "off")

    assert load_settings().reranker == "off"


def test_the_reranker_setting_is_on_or_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASSISTANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ASSISTANT_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("ASSISTANT_RERANKER", "maybe")

    with pytest.raises(SettingsError, match="ASSISTANT_RERANKER"):
        load_settings()


def test_with_reranking_off_no_reranker_is_built_or_checked(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path / "no-models", reranker="off")

    assert reranker_for(settings) is None


def test_with_reranking_on_a_missing_reranker_stops_startup(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path / "no-models", reranker="on")

    with pytest.raises(ModelsNotReady, match=r"BAAI/bge-reranker-v2-m3.*make models"):
        reranker_for(settings)
