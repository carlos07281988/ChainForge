"""Anthropic provider — wraps the Anthropic API into ChainForge's LLM protocol."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message, Role
from chainforge.core.tool import ToolSpec


class AnthropicProvider(BaseModel):
    """Anthropic LLM provider.

    Usage:
        llm = AnthropicProvider(model="claude-sonnet-4-20250514")
        response = await llm.generate(messages)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="claude-sonnet-4-20250514")
    api_key: str | None = Field(default=None)
    max_tokens: int = Field(default=4096)

    def _get_client(self):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError(
                "Anthropic provider requires `anthropic` package. Install with: "
                "pip install 'chainforge[anthropic]'"
            )
        return AsyncAnthropic(
            api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )

    def _to_anthropic_messages(self, messages: list[Message]) -> tuple[list[dict], dict | None]:
        system_msg = None
        msgs = []
        for m in messages:
            if m.role == Role.system:
                system_msg = m.content
                continue
            entry: dict = {"role": m.role.value, "content": []}
            if m.content:
                entry["content"].append({"type": "text", "text": m.content})
            if m.tool_calls:
                for tc in m.tool_calls:
                    entry["content"].append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.args,
                    })
            if m.role == Role.tool:
                entry["content"].append({
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content or "",
                })
            msgs.append(entry)
        return msgs, {"text": system_msg} if system_msg else None

    def _to_tool_specs(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def _parse_response(self, raw: Any) -> LLMResponse:
        content_parts = []
        tool_calls = []
        for block in raw.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": block.input},
                })
        usage = None
        if hasattr(raw, "usage") and raw.usage:
            usage = {
                "input_tokens": raw.usage.input_tokens,
                "output_tokens": raw.usage.output_tokens,
            }
        return LLMResponse(
            content="".join(content_parts) if content_parts else None,
            tool_calls=tool_calls or None,
            usage=usage,
            model=raw.model or self.model,
            finish_reason=raw.stop_reason,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        anthropic_msgs, system = self._to_anthropic_messages(messages)
        anthropic_tools = self._to_tool_specs(tools) if tools else None

        try:
            raw = await client.messages.create(
                model=self.model,
                messages=anthropic_msgs,
                system=system,
                tools=anthropic_tools or None,
                max_tokens=self.max_tokens,
                **kwargs,
            )
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {e}") from e

        return self._parse_response(raw)

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        client = self._get_client()
        anthropic_msgs, system = self._to_anthropic_messages(messages)
        anthropic_tools = self._to_tool_specs(tools) if tools else None

        try:
            async with client.messages.stream(
                model=self.model,
                messages=anthropic_msgs,
                system=system,
                tools=anthropic_tools or None,
                max_tokens=self.max_tokens,
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
                yield self._parse_response(final)
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {e}") from e
