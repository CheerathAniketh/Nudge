"""Provider-neutral types. Agents only ever see these."""

from dataclasses import dataclass
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]
Tier = Literal["cheap", "standard", "reasoning"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    error: str | None = None  # set if the model produced unparseable arguments


@dataclass(frozen=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()  # on assistant messages
    tool_call_id: str | None = None  # on tool-result messages


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: Usage
    model: str
    stop_reason: str = ""

    def as_message(self) -> Message:
        """The assistant message to append to the history before sending tool results."""
        return Message(role="assistant", content=self.text, tool_calls=self.tool_calls)
