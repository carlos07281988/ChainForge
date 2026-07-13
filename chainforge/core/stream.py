"""Streaming primitives — push-based event model for agent execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    text = "text"
    tool_call = "tool_call"
    tool_result = "tool_result"
    error = "error"
    done = "done"
    status = "status"


class StreamEvent(BaseModel):
    """A single event in a stream of agent execution."""

    type: EventType = Field(description="Event type")
    content: str | None = Field(default=None, description="Textual content")
    data: dict[str, Any] = Field(default_factory=dict, description="Structured payload")

    @classmethod
    def text(cls, content: str) -> "StreamEvent":
        return cls(type=EventType.text, content=content)

    @classmethod
    def tool_call(cls, name: str, args: dict[str, Any], id: str = "") -> "StreamEvent":
        return cls(type=EventType.tool_call, data={"name": name, "args": args, "id": id})

    @classmethod
    def tool_result(cls, name: str, content: str, is_error: bool = False) -> "StreamEvent":
        return cls(type=EventType.tool_result, data={"name": name, "content": content, "is_error": is_error})

    @classmethod
    def error(cls, message: str) -> "StreamEvent":
        return cls(type=EventType.error, content=message)

    @classmethod
    def done(cls, content: str | None = None) -> "StreamEvent":
        return cls(type=EventType.done, content=content)

    @classmethod
    def status(cls, message: str) -> "StreamEvent":
        return cls(type=EventType.status, content=message)


class Stream:
    """A wrapper around an async event stream that also provides sync iteration."""

    def __init__(self, async_iter: AsyncIterator[StreamEvent]):
        self._async_iter = async_iter

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self._async_iter

    async def collect_text(self) -> str:
        """Collect all text events into a single string (ignores tool calls, errors, etc.)."""
        parts: list[str] = []
        async for event in self:
            if event.type == EventType.text and event.content:
                parts.append(event.content)
        return "".join(parts)

    async def collect(self) -> list[StreamEvent]:
        """Collect all events into a list."""
        events: list[StreamEvent] = []
        async for event in self:
            events.append(event)
        return events
