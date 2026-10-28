from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration read from `ASSISTANT_*` environment variables (PY-13)."""

    model_config = SettingsConfigDict(env_prefix="ASSISTANT_")

    data_dir: Path
