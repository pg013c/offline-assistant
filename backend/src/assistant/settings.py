from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration read from `ASSISTANT_*` environment variables (PY-13)."""

    model_config = SettingsConfigDict(env_prefix="ASSISTANT_")

    data_dir: Path


class SettingsError(Exception):
    """Configuration is missing or invalid; the message names the environment variables."""


def load_settings() -> Settings:
    """Read settings from the environment, failing with the names of bad variables (GEN-20)."""
    raise NotImplementedError
