"""The chat models `ASSISTANT_CHAT_MODEL` can name, and how each is built (FR-40, AI-23)."""

from dataclasses import dataclass

import httpx

from assistant.adapters.fakes.chat_model import FakeExtractiveChatModel
from assistant.adapters.openai_compatible_chat import LlmServer, OpenAICompatibleChat
from assistant.adapters.pinned_models import QWEN3_8B, PinnedModel
from assistant.ports.chat_model import ChatModel
from assistant.settings import Settings


@dataclass(frozen=True)
class ChatModelSpec:
    """A model by the name configuration uses; `served_model` is None for in-process fakes."""

    served_model: str | None
    pinned: PinnedModel | None
    tools: bool
    json_schema: bool = False
    streaming: bool = False


CHAT_MODELS: dict[str, ChatModelSpec] = {
    "fake-extractive": ChatModelSpec(served_model=None, pinned=None, tools=False),
    "qwen3-8b": ChatModelSpec(served_model="qwen3-8b", pinned=QWEN3_8B, tools=True),
}


class ChatModelNotReady(Exception):
    """The configured model cannot answer; the message says how to start it."""


def chat_model_for(settings: Settings, transport: httpx.BaseTransport | None = None) -> ChatModel:
    """The configured chat model; a served one must be answering before the API starts."""
    spec = CHAT_MODELS[settings.chat_model]
    if spec.served_model is None:
        return FakeExtractiveChatModel()
    _ensure_served(settings.llm_url, spec.served_model, transport)
    return OpenAICompatibleChat(
        model_id=settings.chat_model,
        server=LlmServer(
            base_url=settings.llm_url,
            served_model=spec.served_model,
            timeout_seconds=settings.llm_timeout,
            max_retries=settings.max_retries,
            tools=spec.tools,
        ),
    )


def _ensure_served(url: str, served_model: str, transport: httpx.BaseTransport | None) -> None:
    try:
        with httpx.Client(base_url=url, timeout=5, transport=transport) as client:
            response = client.get("/v1/models")
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise ChatModelNotReady(
            f"No model server answers at {url} (ASSISTANT_LLM_URL). Start it with make llm."
        ) from error
    try:
        served = [model["id"] for model in response.json()["data"]]
    except (ValueError, KeyError, TypeError) as error:
        raise ChatModelNotReady(
            f"The server at {url} (ASSISTANT_LLM_URL) does not list models like an "
            "OpenAI-compatible server. Start the model server with make llm."
        ) from error
    if served_model not in served:
        raise ChatModelNotReady(
            f"The model server at {url} does not serve {served_model}; it serves "
            f"{', '.join(served) or 'nothing'}. Start it with make llm."
        )
