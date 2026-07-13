"""Streaming primitives — push-based event model for agent execution."""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from chainforge.core.structured_output import parse_structured_response
from chainforge.logging import get_logger

logger = get_logger("stream")

T = TypeVar("T", bound=BaseModel)


class EventType(str, Enum):
    text = "text"
    tool_call = "tool_call"
    tool_result = "tool_result"
    error = "error"
    done = "done"
    status = "status"
    state = "state"  # explicit agent state transition


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
    def status(cls, message: str, data: dict | None = None) -> "StreamEvent":
        return cls(type=EventType.status, content=message, data=data or {})

    @classmethod
    def state_transition(cls, to_state: str, message: str | None = None, data: dict | None = None) -> "StreamEvent":
        """Create a state transition event."""
        return cls(type=EventType.state, content=message or to_state, data=data or {"state": to_state})


class Stream:
    """A wrapper around an async event stream with utility methods."""

    def __init__(self, async_iter: AsyncIterator[StreamEvent], response_model: type[BaseModel] | None = None):
        self._async_iter = async_iter
        self._response_model = response_model

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self._async_iter

    async def collect_text(self) -> str:
        """Collect all text events into a single string."""
        parts: list[str] = []
        has_errors = False
        async for event in self:
            if event.type == EventType.text and event.content:
                parts.append(event.content)
            if event.type == EventType.error:
                has_errors = True
        if has_errors:
            logger.warning("collect_text() encountered error events in the stream")
        return "".join(parts)

    async def collect(self) -> list[StreamEvent]:
        """Collect all events into a list."""
        events: list[StreamEvent] = []
        async for event in self:
            events.append(event)
        return events

    async def collect_structured(self, model: type[T] | None = None) -> T | None:
        """Collect the stream and parse the final response into a Pydantic model."""
        response_model = model or self._response_model
        if response_model is None:
            raise ValueError(
                "No response_model provided. Either pass one to collect_structured() "
                "or set response_model when calling agent.run()"
            )
        text = await self.collect_text()
        if not text:
            return None
        return parse_structured_response(text, response_model)

    async def collect_states(self) -> list[dict]:
        """Collect only state transition events with metadata."""
        states: list[dict] = []
        async for event in self:
            if event.type == EventType.state:
                states.append({
                    "state": event.data.get("state", event.content),
                    "message": event.content,
                    "data": event.data,
                })
        return states
