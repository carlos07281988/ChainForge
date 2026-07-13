"""Message types — the universal conversation primitives."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    id: str = Field(description="Unique identifier for this tool call")
    name: str = Field(description="Tool name")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResult(BaseModel):
    """The result of executing a tool call."""

    tool_call_id: str = Field(description="Matching ToolCall.id")
    name: str = Field(description="Tool name")
    content: str = Field(default="", description="Tool output content")
    is_error: bool = Field(default=False, description="Whether the tool raised")


class Message(BaseModel):
    """A single message in a conversation."""

    role: Role = Field(description="Message role")
    content: str | None = Field(default=None, description="Text content")
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls from assistant")
    tool_call_id: str | None = Field(default=None, description="Tool result reference")
    name: str | None = Field(default=None, description="Tool name for tool results")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")

    @classmethod
    def system(cls, content: str, **kwargs) -> "Message":
        return cls(role=Role.system, content=content, **kwargs)

    @classmethod
    def user(cls, content: str, **kwargs) -> "Message":
        return cls(role=Role.user, content=content, **kwargs)

    @classmethod
    def assistant(cls, content: str | None = None, tool_calls: list[ToolCall] | None = None, **kwargs) -> "Message":
        return cls(role=Role.assistant, content=content, tool_calls=tool_calls, **kwargs)

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str, is_error: bool = False) -> "Message":
        return cls(
            role=Role.tool,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
            metadata={"is_error": is_error},
        )

    def model_dump_openai(self) -> dict:
        """Dump to OpenAI-compatible dict."""
        base = {"role": self.role.value}
        if self.content is not None:
            base["content"] = self.content
        if self.tool_calls:
            base["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.args},
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            base["tool_call_id"] = self.tool_call_id
        if self.name:
            base["name"] = self.name
        return base
