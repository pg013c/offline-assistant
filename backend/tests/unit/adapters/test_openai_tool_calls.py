"""Tool calls through the OpenAI-compatible adapter against a stub server (F-07 groundwork)."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field

from assistant.adapters.openai_compatible_chat import LlmServer, OpenAICompatibleChat
from assistant.domain.answers import ModelFailed
from assistant.domain.tools import (
    FinalText,
    Message,
    ToolCall,
    ToolCalls,
    ToolSpec,
    ToolsUnsupported,
)


class SearchArguments(BaseModel):
    query: str = Field(min_length=1)


SEARCH = ToolSpec(
    name="search_documents", description="Search the uploaded documents.", arguments=SearchArguments
)
ASKED = [Message(role="user", content="What does the AI Act say about logs?")]


def completion(message: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"index": 0, "message": message}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 20},
        },
    )


def calling(name: str, arguments: str, call_id: str = "call-1") -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}
        ],
    }


class StubServer:
    def __init__(self, *messages: dict[str, Any]) -> None:
        self._messages = list(messages)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        return completion(self._messages.pop(0))


def model(
    server: Callable[[httpx.Request], httpx.Response], *, tools: bool = True, max_retries: int = 2
) -> OpenAICompatibleChat:
    return OpenAICompatibleChat(
        model_id="qwen3-8b",
        server=LlmServer(
            base_url="http://127.0.0.1:8080",
            served_model="qwen3-8b",
            timeout_seconds=30,
            max_retries=max_retries,
            tools=tools,
        ),
        transport=httpx.MockTransport(server),
    )


def turn(
    chat: OpenAICompatibleChat, messages: list[Message] = ASKED
) -> ToolCalls | FinalText | ModelFailed:
    return asyncio.run(chat.call_tools(messages, [SEARCH]))


def test_the_tools_are_sent_as_function_schemas() -> None:
    server = StubServer(calling("search_documents", '{"query": "logs"}'))

    turn(model(server))

    request = server.requests[0]
    assert request["stream"] is False
    assert request["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Search the uploaded documents.",
                "parameters": SearchArguments.model_json_schema(),
            },
        }
    ]
    assert request["messages"] == [
        {"role": "user", "content": "What does the AI Act say about logs?"}
    ]


def test_a_tool_turn_is_capped_far_below_an_answer() -> None:
    server = StubServer(calling("search_documents", '{"query": "logs"}'))

    turn(model(server))

    assert server.requests[0]["max_tokens"] == 256


def test_a_tool_call_comes_back_with_validated_arguments() -> None:
    result = turn(model(StubServer(calling("search_documents", '{"query": "logs"}'))))

    assert result == ToolCalls(
        (ToolCall(id="call-1", name="search_documents", arguments=SearchArguments(query="logs")),)
    )


def test_an_answer_without_a_tool_call_is_final_text() -> None:
    result = turn(model(StubServer({"role": "assistant", "content": "Logs are kept."})))

    assert result == FinalText("Logs are kept.")


def test_invalid_arguments_are_retried_with_the_error() -> None:
    server = StubServer(
        calling("search_documents", '{"query": ""}'),
        calling("search_documents", '{"query": "logs"}', call_id="call-2"),
    )

    result = turn(model(server))

    assert isinstance(result, ToolCalls)
    retry = server.requests[1]["messages"]
    assert retry[-1]["role"] == "tool"
    assert retry[-1]["tool_call_id"] == "call-1"
    assert "query" in retry[-1]["content"]


def test_an_unknown_tool_is_retried_and_then_fails() -> None:
    server = StubServer(
        calling("delete_everything", "{}"), calling("delete_everything", "{}", call_id="call-2")
    )

    result = turn(model(server, max_retries=1))

    assert isinstance(result, ModelFailed)
    assert result.code == "invalid_answer"
    assert "delete_everything" in result.detail


def test_earlier_tool_calls_and_results_are_sent_back_in_order() -> None:
    server = StubServer({"role": "assistant", "content": "Six months."})
    call = ToolCall(id="call-1", name="search_documents", arguments=SearchArguments(query="logs"))
    history = [
        *ASKED,
        Message(role="assistant", content="", tool_calls=(call,)),
        Message(
            role="tool", content="Passage 1: logs are kept for six months.", tool_call_id="call-1"
        ),
    ]

    turn(model(server), history)

    sent = server.requests[0]["messages"]
    assert sent[1]["tool_calls"] == [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "search_documents", "arguments": '{"query":"logs"}'},
        }
    ]
    assert sent[2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "Passage 1: logs are kept for six months.",
    }


def test_a_model_not_declared_able_to_call_tools_is_refused_before_any_request() -> None:
    server = StubServer()

    with pytest.raises(ToolsUnsupported, match="qwen3-8b"):
        turn(model(server, tools=False))

    assert server.requests == []


def test_a_completion_body_that_is_not_json_is_a_model_error() -> None:
    def server(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>proxy error</html>")

    result = turn(model(server))

    assert isinstance(result, ModelFailed)
    assert result.code == "model_error"


def test_a_tool_turn_records_its_usage() -> None:
    result = turn(model(StubServer(calling("search_documents", '{"query": "logs"}'))))

    assert isinstance(result, ToolCalls)
    assert result.usage is not None
    assert (result.usage.prompt_tokens, result.usage.completion_tokens) == (150, 20)
    assert result.usage.attempts == 1
