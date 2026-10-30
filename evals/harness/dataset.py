"""Evaluation cases, loaded from YAML and checked against their JSON schema (TEST-20)."""

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).parents[1] / "datasets" / "retrieval.schema.json"
# The answer suite's own cases may also expect tools, forbid strings or expect "not covered".
ANSWER_SCHEMA = SCHEMA.with_name("answers.schema.json")


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
    # Answer suite only: tools any of which should be called, strings the answer must not hold.
    tools: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    # Answer suite only: whether the answer must save a note (F-07a).
    note: bool = False
    # Answer suite only: the key points a correct answer makes, for the judge (F-09a).
    key_points: tuple[str, ...] = ()


def load_cases(path: Path) -> list[Case]:
    """The cases of a dataset file, each validated against the schema."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _validated(document["cases"])


def _validated(entries: list[dict[str, Any]], schema: Path = SCHEMA) -> list[Case]:
    validator = Draft202012Validator(json.loads(schema.read_text(encoding="utf-8")))
    cases: list[Case] = []
    for entry in entries:
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
        tools=tuple(expected.get("tools", ())),
        forbidden=tuple(expected.get("forbidden", ())),
        note=bool(expected.get("note", False)),
        key_points=tuple(expected.get("key_points", ())),
    )


def load_answer_cases(path: Path) -> list[Case]:
    """The answer suite: the reused retrieval cases with their reference answers, then the
    suite's own cases (F-06, F-07, F-09a)."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    reused = load_cases(path.parent / document["reuse"])
    references: dict[str, list[str]] = document.get("references") or {}
    unknown = set(references) - {case.id for case in reused}
    if unknown:
        raise DatasetError(f"references name no reused case: {', '.join(sorted(unknown))}")
    reused = [replace(case, key_points=tuple(references.get(case.id, ()))) for case in reused]
    return reused + _validated(document["cases"], ANSWER_SCHEMA)
