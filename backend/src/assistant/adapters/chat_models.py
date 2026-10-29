"""The chat models `ASSISTANT_CHAT_MODEL` can name, and how each is built (FR-40, AI-23)."""

from dataclasses import dataclass

import httpx

from assistant.adapters.pinned_models import PinnedModel
from assistant.ports.chat_model import ChatModel
from assistant.settings import Settings


@dataclass(frozen=True)
class ChatModelSpec:
    served_model: str | None
    pinned: PinnedModel | None
    tools: bool


CHAT_MODELS: dict[str, ChatModelSpec] = {}


class ChatModelNotReady(Exception):
    """The configured model cannot answer; the message says how to start it."""


def chat_model_for(settings: Settings, transport: httpx.BaseTransport | None = None) -> ChatModel:
    raise NotImplementedError
