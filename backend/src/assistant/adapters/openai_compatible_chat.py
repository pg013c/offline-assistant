"""A chat model behind any OpenAI-compatible server: llama.cpp, Ollama, MLX, vLLM (ADR 0003).

The answer is asked for as JSON against `ANSWER_SCHEMA`; its text streams while the model
writes it, and an invalid answer is retried with the reason fed back (AI-21).
"""

import json
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

import httpx
from pydantic import ValidationError

from assistant.domain.answers import (
    ANSWER_SCHEMA,
    Answered,
    AnswerTextExtractor,
    AttemptDiscarded,
    InvalidAnswer,
    ModelEvent,
    ModelFailed,
    TextDelta,
    Usage,
    parse_answer,
)
from assistant.domain.documents import Chunk, indexed_text
from assistant.domain.tools import (
    FinalText,
    Message,
    ToolCall,
    ToolCalls,
    ToolSpec,
    ToolsUnsupported,
)

ANSWER_PROMPT = files("assistant").joinpath("prompts/answer.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class LlmServer:
    """Where a model is served and how long and how often to try it (AI-21, AI-22)."""

    base_url: str
    served_model: str
    timeout_seconds: float
    max_retries: int
    # Capabilities are declared, not guessed from the model's name (AI-23).
    tools: bool = True


@dataclass
class _Tally:
    """Tokens and timings over every attempt of one answer."""

    started: float = field(default_factory=time.monotonic)
    first_token: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    attempts: int = 0

    def usage(self) -> Usage:
        return Usage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            first_token_ms=None
            if self.first_token is None
            else _ms(self.first_token - self.started),
            total_ms=_ms(time.monotonic() - self.started),
            attempts=self.attempts,
        )


class _Unanswered(Exception):
    def __init__(self, failure: ModelFailed) -> None:
        super().__init__(failure.detail)
        self.failure = failure


class OpenAICompatibleChat:
    is_test_model = False

    def __init__(
        self,
        *,
        model_id: str,
        server: LlmServer,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = model_id
        self._server = server
        self._transport = transport

    async def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": ANSWER_PROMPT},
            {"role": "user", "content": _user_message(question, passages)},
        ]
        tally = _Tally()
        async with httpx.AsyncClient(
            base_url=self._server.base_url,
            timeout=self._server.timeout_seconds,
            transport=self._transport,
        ) as client:
            while True:
                tally.attempts += 1
                output: list[str] = []
                try:
                    async for event in self._attempt(client, messages, tally, output):
                        yield event
                except _Unanswered as error:
                    yield error.failure
                    return
                raw = "".join(output)
                try:
                    answer = parse_answer(raw, len(passages))
                except InvalidAnswer as error:
                    reason = str(error)
                    yield AttemptDiscarded(reason)
                    if tally.attempts > self._server.max_retries:
                        yield ModelFailed(
                            "invalid_answer",
                            f"The model gave no valid answer after {tally.attempts} attempts; "
                            f"the last one was rejected because {reason}.",
                        )
                        return
                    messages += [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": f"Your reply was rejected: {reason}. Reply again with "
                            "the JSON object only, citing passages by their numbers.",
                        },
                    ]
                    continue
                yield Answered(answer, tally.usage())
                return

    async def _attempt(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, str]],
        tally: _Tally,
        output: list[str],
    ) -> AsyncIterator[ModelEvent]:
        """One streamed completion: its answer text as deltas, its raw output into `output`."""
        url = self._server.base_url
        extractor = AnswerTextExtractor()
        try:
            async with client.stream(
                "POST", "/v1/chat/completions", json=self._body(messages)
            ) as response:
                if response.status_code != httpx.codes.OK:
                    await response.aread()
                    raise _Unanswered(_error_status(url, response))
                async for line in response.aiter_lines():
                    chunk = _chunk(line)
                    if chunk is None:
                        continue
                    _count(chunk, tally)
                    content = _content(chunk)
                    if not content:
                        continue
                    output.append(content)
                    text = extractor.feed(content)
                    if text:
                        if tally.first_token is None:
                            tally.first_token = time.monotonic()
                        yield TextDelta(text)
        except httpx.TimeoutException as error:
            raise _Unanswered(_timed_out(url, self._server.timeout_seconds)) from error
        except httpx.TransportError as error:
            raise _Unanswered(_unreachable(url)) from error
        except ValueError as error:
            raise _Unanswered(_not_json(url)) from error

    async def call_tools(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ToolCalls | FinalText | ModelFailed:
        """The model's next turn; invalid calls are retried with the error fed back (AI-21)."""
        if not self._server.tools:
            raise ToolsUnsupported(f"{self.model_id} is not configured to call tools")
        by_name = {tool.name: tool for tool in tools}
        sent = [_wire(message) for message in messages]
        async with httpx.AsyncClient(
            base_url=self._server.base_url,
            timeout=self._server.timeout_seconds,
            transport=self._transport,
        ) as client:
            for attempt in range(1, self._server.max_retries + 2):
                try:
                    reply = await self._complete(client, sent, tools)
                except _Unanswered as error:
                    return error.failure
                raw_calls = reply.get("tool_calls") or []
                if not raw_calls:
                    return FinalText(reply.get("content") or "")
                calls, errors = _parse_calls(raw_calls, by_name)
                if not errors:
                    return ToolCalls(tuple(calls))
                if attempt > self._server.max_retries:
                    break
                sent += [
                    {
                        "role": "assistant",
                        "content": reply.get("content") or "",
                        "tool_calls": raw_calls,
                    },
                    *(
                        {"role": "tool", "tool_call_id": call_id, "content": f"Error: {error}"}
                        for call_id, error in errors
                    ),
                ]
        return ModelFailed(
            "invalid_answer",
            f"The model made no valid tool call after {attempt} attempts: {errors[0][1]}",
        )

    async def _complete(
        self, client: httpx.AsyncClient, messages: list[dict[str, Any]], tools: Sequence[ToolSpec]
    ) -> dict[str, Any]:
        """One non-streamed completion with tools; its message."""
        url = self._server.base_url
        body = {
            "model": self._server.served_model,
            "messages": messages,
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.arguments.model_json_schema(),
                    },
                }
                for tool in tools
            ],
            "temperature": 0,
        }
        try:
            response = await client.post("/v1/chat/completions", json=body)
        except httpx.TimeoutException as error:
            raise _Unanswered(_timed_out(url, self._server.timeout_seconds)) from error
        except httpx.TransportError as error:
            raise _Unanswered(_unreachable(url)) from error
        if response.status_code != httpx.codes.OK:
            raise _Unanswered(_error_status(url, response))
        try:
            message: dict[str, Any] = response.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise _Unanswered(_not_json(url)) from error
        return message

    def _body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self._server.served_model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": ANSWER_SCHEMA},
            },
            # Answers should follow the passages, not vary between runs.
            "temperature": 0,
        }


def _wire(message: Message) -> dict[str, Any]:
    """A conversation message as the Chat Completions API takes it."""
    wired: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wired["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments.model_dump_json()},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wired["tool_call_id"] = message.tool_call_id
    return wired


def _parse_calls(
    raw_calls: list[dict[str, Any]], tools: dict[str, ToolSpec]
) -> tuple[list[ToolCall], list[tuple[str, str]]]:
    """The valid calls, and (call id, error) for each invalid one."""
    calls: list[ToolCall] = []
    errors: list[tuple[str, str]] = []
    for raw in raw_calls:
        call_id = str(raw.get("id", ""))
        function = raw.get("function", {})
        name = function.get("name", "")
        tool = tools.get(name)
        if tool is None:
            errors.append((call_id, f"there is no tool {name}; use one of {', '.join(tools)}"))
            continue
        try:
            arguments = tool.arguments.model_validate_json(function.get("arguments") or "{}")
        except ValidationError as error:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                for issue in error.errors()
            )
            errors.append((call_id, f"invalid arguments for {name}: {problems}"))
            continue
        calls.append(ToolCall(id=call_id, name=name, arguments=arguments))
    return calls, errors


def _unreachable(url: str) -> ModelFailed:
    return ModelFailed(
        "model_unreachable", f"No model server answers at {url}. Start it with make llm."
    )


def _timed_out(url: str, seconds: float) -> ModelFailed:
    return ModelFailed(
        "model_timeout", f"The model server at {url} did not answer within {seconds:g} s."
    )


def _not_json(url: str) -> ModelFailed:
    return ModelFailed(
        "model_error", f"The model server at {url} sent a response that is not valid JSON."
    )


def _error_status(url: str, response: httpx.Response) -> ModelFailed:
    return ModelFailed(
        "model_error",
        f"The model server at {url} answered {response.status_code}: {response.text[:200]}",
    )


def _user_message(question: str, passages: Sequence[Chunk]) -> str:
    # Passages are delimited data, each with its heading path for context (AI-10).
    blocks = [
        f'<passage number="{number}">\n{indexed_text(chunk)}\n</passage>'
        for number, chunk in enumerate(passages, start=1)
    ]
    return "\n\n".join([*blocks, f"Question: {question}"])


def _chunk(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None
    data = line.removeprefix("data:").strip()
    if not data or data == "[DONE]":
        return None
    decoded: dict[str, Any] = json.loads(data)
    return decoded


def _count(chunk: dict[str, Any], tally: _Tally) -> None:
    usage = chunk.get("usage")
    if usage:
        tally.prompt_tokens += int(usage.get("prompt_tokens", 0))
        tally.completion_tokens += int(usage.get("completion_tokens", 0))


def _content(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""
    content = choices[0].get("delta", {}).get("content")
    return content if isinstance(content, str) else ""


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)
