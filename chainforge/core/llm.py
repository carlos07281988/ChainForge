"""LLM abstraction — provider-agnostic interface for language models."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec


class LLMResponse(BaseModel):
    """A structured response from an LLM."""

    content: str | None = Field(default=None, description="Text output")
    tool_calls: list[dict[str, Any]] | None = Field(default=None, description="Tool calls requested")
    usage: dict[str, int] | None = Field(default=None, description="Token usage info")
    model: str = Field(default="", description="Model name")
    finish_reason: str | None = Field(default=None)


@runtime_checkable
class LLM(Protocol):
    """Protocol for any LLM provider."""

    model: str
    """Model identifier string."""

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a complete response (non-streaming)."""
        ...

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream tokens, yielding strings and a final LLMResponse."""
        ...
