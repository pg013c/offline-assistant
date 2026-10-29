"""Tools a language model may call, and the conversation that carries the calls (F-07)."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


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


@dataclass(frozen=True, slots=True)
class FinalText:
    """The model answered without calling a tool."""

    text: str


class ToolsUnsupported(Exception):
    """The configured model is not declared able to call tools (AI-23)."""
