"""Contract for the ToolCallingModel port; the fake and the stubbed adapter must pass it."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field

from assistant.adapters.fakes.chat_model import ScriptedToolCallingModel
from assistant.adapters.openai_compatible_chat import LlmServer, OpenAICompatibleChat
from assistant.domain.answers import ModelFailed
from assistant.domain.tools import FinalText, Message, ToolCalls, ToolSpec
from assistant.ports.chat_model import ToolCallingModel


class SearchArguments(BaseModel):
    query: str = Field(min_length=1)


SEARCH = ToolSpec(name="search_documents", description="Search.", arguments=SearchArguments)
ASKED = [Message(role="user", content="What does the AI Act say about logs?")]

# Each reply is (tool name and JSON arguments) or plain text; scripts are replayed in order.
type Reply = tuple[str, str] | str


def scripted(replies: list[Reply]) -> ToolCallingModel:
    return ScriptedToolCallingModel(replies, max_retries=1)


def stubbed(replies: list[Reply]) -> ToolCallingModel:
    pending = list(replies)

    def server(request: httpx.Request) -> httpx.Response:
        reply = pending.pop(0)
        message: dict[str, Any]
        if isinstance(reply, str):
            message = {"role": "assistant", "content": reply}
        else:
            name, arguments = reply
            call = {
                "id": "c1",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
            message = {"role": "assistant", "content": "", "tool_calls": [call]}
        return httpx.Response(200, json={"choices": [{"message": message}], "usage": {}})

    return OpenAICompatibleChat(
        model_id="stub",
        server=LlmServer(
            base_url="http://127.0.0.1:8080", served_model="stub", timeout_seconds=5, max_retries=1
        ),
        transport=httpx.MockTransport(server),
    )


ADAPTERS: list[Callable[[list[Reply]], ToolCallingModel]] = [scripted, stubbed]


@pytest.fixture(params=ADAPTERS, ids=["scripted", "openai-compatible-stub"])
def build(request: pytest.FixtureRequest) -> Callable[[list[Reply]], ToolCallingModel]:
    factory: Callable[[list[Reply]], ToolCallingModel] = request.param
    return factory


def turn(model: ToolCallingModel) -> ToolCalls | FinalText | ModelFailed:
    return asyncio.run(model.call_tools(ASKED, [SEARCH]))


def test_a_valid_call_comes_back_with_typed_arguments(
    build: Callable[[list[Reply]], ToolCallingModel],
) -> None:
    result = turn(build([("search_documents", json.dumps({"query": "logs"}))]))

    assert isinstance(result, ToolCalls)
    [call] = result.calls
    assert call.name == "search_documents"
    assert call.arguments == SearchArguments(query="logs")


def test_a_reply_without_a_call_is_final_text(
    build: Callable[[list[Reply]], ToolCallingModel],
) -> None:
    assert turn(build(["Logs are kept for six months."])) == FinalText(
        "Logs are kept for six months."
    )


def test_invalid_calls_are_retried_and_then_fail(
    build: Callable[[list[Reply]], ToolCallingModel],
) -> None:
    result = turn(build([("search_documents", '{"query": ""}'), ("delete_everything", "{}")]))

    assert isinstance(result, ModelFailed)
    assert result.code == "invalid_answer"
