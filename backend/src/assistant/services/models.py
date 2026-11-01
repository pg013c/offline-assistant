"""The models a question can be answered with, and which is the default (F-08)."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from assistant.domain.errors import UnknownModel
from assistant.ports.chat_model import ChatModel
from assistant.services.questions import Answerer


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """A model the API can answer with, and what answers with it."""

    id: str
    is_test_model: bool
    answerer: Answerer
    # Asked whether it answers each time the models are listed (F-09b).
    model: ChatModel


@dataclass(frozen=True, slots=True)
class ModelChoice:
    id: str
    is_test_model: bool
    is_default: bool


class ChatModels:
    """The configured model first, as the default, then any others offered beside it."""

    def __init__(self, entries: Sequence[ModelEntry]) -> None:
        if not entries:
            raise ValueError("the API needs at least one model to answer with")
        self._entries: dict[str, ModelEntry] = {}
        for entry in entries:
            if entry.id in self._entries:
                raise ValueError(f"{entry.id} is listed twice among the models")
            self._entries[entry.id] = entry
        self._default = entries[0].id

    async def list_models(self) -> list[ModelChoice]:
        """The models that answer now; one whose server stops is left out until it answers."""
        entries = list(self._entries.values())
        available = await asyncio.gather(*(entry.model.is_available() for entry in entries))
        return [
            ModelChoice(
                id=entry.id, is_test_model=entry.is_test_model, is_default=entry.id == self._default
            )
            for entry, answers in zip(entries, available, strict=True)
            if answers
        ]

    def answerer(self, model_id: str | None) -> Answerer:
        """What answers with this model, or with the default; `UnknownModel` if none does."""
        entry = self._entries.get(model_id or self._default)
        if entry is None:
            raise UnknownModel(
                f"There is no model {model_id}; the models are {', '.join(self._entries)}."
            )
        return entry.answerer
