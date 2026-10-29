"""Evaluation cases, loaded from YAML and checked against their JSON schema (TEST-20)."""

from dataclasses import dataclass
from pathlib import Path


class DatasetError(Exception):
    """A case breaks the schema; the message names the case."""


@dataclass(frozen=True)
class ExpectedSource:
    document: str
    article: str | None = None
    paragraph: str | None = None
    heading: str | None = None


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    language: str
    question: str
    behaviour: str
    sources: tuple[ExpectedSource, ...]


def load_cases(path: Path) -> list[Case]:
    raise NotImplementedError
