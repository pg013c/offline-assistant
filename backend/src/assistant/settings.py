from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "ASSISTANT_"


class Settings(BaseSettings):
    """Typed configuration read from `ASSISTANT_*` environment variables (PY-13)."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    data_dir: Path


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
