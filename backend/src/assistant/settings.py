import ipaddress
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "ASSISTANT_"

# A single-label host such as a Compose service name. It must start with a letter, because
# resolvers read a bare number like `3232235777` or `0x7f000001` as an IP address.
SERVICE_NAME = re.compile(r"[a-z][a-z0-9_-]*")


def is_local_host(host: str) -> bool:
    """Whether a URL host stays on this machine: loopback, `localhost` or a service name."""
    if host == "localhost" or SERVICE_NAME.fullmatch(host):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def url_problem(url: str, *, allow_network: bool) -> str | None:
    """Why a service URL is refused, or None; names only the host, never credentials (ADR 0004)."""
    try:
        parts = urlsplit(url)
    except ValueError:  # an unclosed IPv6 bracket, for one
        return "must be an http or https URL"
    host = parts.hostname
    if parts.scheme not in {"http", "https"} or not host:
        return "must be an http or https URL"
    if not allow_network and not is_local_host(host):
        return (
            f"points to {host!r}, which is not this machine: use localhost, 127.0.0.0/8, ::1"
            " or a Compose service name, or set ASSISTANT_ALLOW_NETWORK=1 (ADR 0004)"
        )
    return None


class Settings(BaseSettings):
    """Typed configuration read from `ASSISTANT_*` environment variables (PY-13)."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    data_dir: Path
    # A name from `adapters.chat_models`; the test model needs no server (FR-40).
    chat_model: Literal[
        "fake-extractive",
        "qwen3.5-9b",
        "qwen3.6-35b-a3b",
        "gemma-4-26b-a4b",
    ] = "fake-extractive"
    # The OpenAI-compatible server `make llm` starts (ADR 0021), a call's timeout in seconds
    # (AI-22) and how often a rejected answer is retried (AI-21). The URL, like `qdrant_url`,
    # must stay on this machine unless network mode is on.
    llm_url: str = "http://127.0.0.1:8080"
    llm_timeout: float = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    # Model turns that may call tools before the answer (AI-22, F-07).
    max_tool_turns: int = Field(default=2, ge=1, le=10)
    # Where the agent saves notes (F-07a, AI-11); `<data_dir>/notes` unless set.
    notes_dir: Path = Path()
    # Comparison mode may use the network (ADR 0004); nothing does until F-09.
    allow_network: bool = False
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

    # A model validator, since `llm_url` is read before `allow_network`.
    @model_validator(mode="after")
    def _services_stay_local(self) -> "Settings":
        problems = []
        for name, url in (("llm_url", self.llm_url), ("qdrant_url", self.qdrant_url)):
            problem = url_problem(url, allow_network=self.allow_network)
            if problem:
                problems.append(f"{variable_name((name,))} {problem}")
        if problems:
            raise ValueError("; ".join(problems))
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
