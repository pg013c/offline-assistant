"""The models a question can be answered with, and which is the default (F-08)."""

from collections.abc import Sequence
from dataclasses import dataclass

from assistant.services.questions import Answerer


@dataclass(frozen=True, slots=True)
class ModelEntry:
    id: str
    is_test_model: bool
    answerer: Answerer


@dataclass(frozen=True, slots=True)
class ModelChoice:
    id: str
    is_test_model: bool
    is_default: bool


class ChatModels:
    def __init__(self, entries: Sequence[ModelEntry]) -> None:
        raise NotImplementedError

    def list_models(self) -> list[ModelChoice]:
        raise NotImplementedError

    def answerer(self, model_id: str | None) -> Answerer:
        raise NotImplementedError
