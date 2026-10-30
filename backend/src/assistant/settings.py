from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "ASSISTANT_"


class Settings(BaseSettings):
    """Typed configuration read from `ASSISTANT_*` environment variables (PY-13)."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    data_dir: Path
    # A name from `adapters.chat_models`; the test model needs no server (FR-40).
    chat_model: Literal["fake-extractive", "qwen3-8b"] = "fake-extractive"
    # The OpenAI-compatible server `make llm` starts (ADR 0021), a call's timeout in seconds
    # (AI-22) and how often a rejected answer is retried (AI-21).
    llm_url: str = "http://127.0.0.1:8080"
    llm_timeout: float = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    # Model turns that may call tools before the answer (AI-22, F-07).
    max_tool_turns: int = Field(default=2, ge=1, le=10)
    # Where the agent saves notes (F-07a, AI-11); `<data_dir>/notes` unless set.
    notes_dir: Path = Path()
    # `docling` reads every supported format; `text-only` reads .txt and .md without models.
    document_parser: Literal["docling", "text-only"] = "docling"
    # Where `make models` put the parsing and embedding models (ADR 0004).
    models_dir: Path
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection_prefix: str = "assistant"
    # Dense similarity a passage needs to be cited; tuned on the fixtures (F-03), measured in F-04.
    min_similarity: float = Field(default=0.5, ge=0, le=1)
    # Reorder search candidates with the cross-encoder (F-05, ADR 0019); `auto` uses it with
    # an Apple GPU only, since on a CPU it costs seconds per question.
    reranker: Literal["on", "off", "auto"] = "auto"

    @model_validator(mode="after")
    def _notes_under_the_data_dir(self) -> "Settings":
        if "notes_dir" not in self.model_fields_set:
            self.notes_dir = self.data_dir / "notes"
        return self


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
