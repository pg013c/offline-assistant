"""Evaluation cases, loaded from YAML and checked against their JSON schema (TEST-20)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).parents[1] / "datasets" / "retrieval.schema.json"


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
    """The cases of a dataset file, each validated against the schema."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    cases: list[Case] = []
    for entry in document["cases"]:
        errors = sorted(validator.iter_errors(entry), key=lambda error: list(error.path))
        if errors:
            problems = "; ".join(error.message for error in errors)
            raise DatasetError(f"{entry.get('id', '?')}: {problems}")
        cases.append(_case(entry))
    return cases


def _case(entry: dict[str, Any]) -> Case:
    expected = entry["expected"]
    return Case(
        id=entry["id"],
        kind=entry["kind"],
        language=entry["language"],
        question=entry["question"],
        behaviour=expected["behaviour"],
        sources=tuple(ExpectedSource(**source) for source in expected["sources"]),
    )


def load_answer_cases(path: Path) -> list[Case]:
    """The answer suite: the reused retrieval cases, then the suite's own (F-06)."""
    raise NotImplementedError
