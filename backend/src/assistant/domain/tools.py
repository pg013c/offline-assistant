"""Tools a language model may call, and the conversation that carries the calls (F-07)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ValidationError

from assistant.domain.answers import Usage


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool the model may call; its arguments are a Pydantic model (AI-20)."""

    name: str
    description: str
    arguments: type[BaseModel]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: BaseModel


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCalls:
    """The model wants these tools run before it answers."""

    calls: tuple[ToolCall, ...]
    usage: Usage | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class FinalText:
    """The model answered without calling a tool."""

    text: str
    usage: Usage | None = field(default=None, compare=False)


class ToolsUnsupported(Exception):
    """The configured model is not declared able to call tools (AI-23)."""


def parse_tool_calls(
    raw_calls: Sequence[tuple[str, str, str]], tools: Mapping[str, ToolSpec]
) -> tuple[list[ToolCall], list[tuple[str, str]]]:
    """Calls given as (id, tool name, JSON arguments): the valid ones with typed arguments,
    and (id, error) for each invalid one, worded for the model to correct (AI-21)."""
    calls: list[ToolCall] = []
    errors: list[tuple[str, str]] = []
    for call_id, name, arguments in raw_calls:
        tool = tools.get(name)
        if tool is None:
            errors.append((call_id, f"there is no tool {name}; use one of {', '.join(tools)}"))
            continue
        try:
            parsed = tool.arguments.model_validate_json(arguments)
        except ValidationError as error:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                for issue in error.errors()
            )
            errors.append((call_id, f"invalid arguments for {name}: {problems}"))
            continue
        calls.append(ToolCall(id=call_id, name=name, arguments=parsed))
    return calls, errors
