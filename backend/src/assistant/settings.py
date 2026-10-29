from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "ASSISTANT_"


class Settings(BaseSettings):
    """Typed configuration read from `ASSISTANT_*` environment variables (PY-13)."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    data_dir: Path
    # The only chat model until F-06 adds real ones.
    chat_model: Literal["fake-extractive"] = "fake-extractive"
    # `docling` reads every supported format; `text-only` reads .txt and .md without models.
    document_parser: Literal["docling", "text-only"] = "docling"
    # Where `make models` put the parsing and embedding models (ADR 0004).
    models_dir: Path | None = Field(default=None, validate_default=True)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection_prefix: str = "assistant"
    min_similarity: float = 0.5

    @field_validator("models_dir")
    @classmethod
    def _required_by_docling(cls, value: Path | None, info: ValidationInfo) -> Path | None:
        if value is None and info.data.get("document_parser") == "docling":
            raise ValueError("required by the Docling document parser; run `make models`")
        return value


class SettingsError(Exception):
    """Configuration is missing or invalid; the message names the environment variables."""


def variable_name(location: tuple[int | str, ...]) -> str:
    """The environment variable behind a validation error location."""
    if not location:
        return f"{ENV_PREFIX}* settings"
    return ENV_PREFIX + "_".join(str(part) for part in location).upper()


def load_settings() -> Settings:
    """Read settings from the environment, failing with the names of bad variables (GEN-20)."""
    try:
        # Values come from the environment, which mypy cannot see.
        return Settings()  # type: ignore[call-arg]
    except ValidationError as error:
        problems = "; ".join(
            f"{variable_name(issue['loc'])}: {issue['msg']}" for issue in error.errors()
        )
        raise SettingsError(f"Invalid configuration. {problems}") from error
