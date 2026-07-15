# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""DeepSeek provider — supports DeepSeek-V3 (chat) and DeepSeek-R1 (reasoner).

Uses the OpenAI-compatible API at api.deepseek.com.
Properly handles reasoning_content from the DeepSeek-R1 model.

Usage:
    from chainforge.providers import DeepSeekProvider

    llm = DeepSeekProvider(model="deepseek-reasoner")  # R1 with reasoning
    llm = DeepSeekProvider(model="deepseek-chat")       # V3 chat
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from logging import DEBUG, WARNING
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse, ProviderCapability
from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec
from chainforge.logging import get_logger, log_data

logger = get_logger("providers.deepseek")


class DeepSeekProvider(BaseModel):
    """DeepSeek LLM provider via OpenAI-compatible API.

    Supports:
    - deepseek-chat: DeepSeek-V3 standard chat
    - deepseek-reasoner: DeepSeek-R1 with reasoning_content output
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="deepseek-chat")
    api_key: str | None = Field(default=None)
    base_url: str = Field(default="https://api.deepseek.com/v1")

    @property
    def capabilities(self) -> set[str]:
        caps = {
            ProviderCapability.CHAT, ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING, ProviderCapability.FUNCTION_CALLING,
        }
        if "reasoner" in self.model.lower():
            caps.add(ProviderCapability.REASONING)
        return caps

    def _get_client(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("DeepSeek provider requires `openai` package.")
        return AsyncOpenAI(
            api_key=self.api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url=self.base_url,
        )

    def _to_openai_messages(self, messages: list[Message]) -> list[dict]:
        return [m.model_dump_openai() for m in messages]

    def _to_tool_specs(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters,
            }}
            for t in tools
        ]

    def _parse_response(self, raw: Any) -> LLMResponse:
        """Parse API response, extracting reasoning_content for deepseek-reasoner."""
        choice = raw.choices[0]
        msg = choice.message

        # Extract reasoning_content (DeepSeek-R1 specific field)
        reasoning_content = getattr(msg, "reasoning_content", None)
        if reasoning_content is None:
            # Try dict access
            msg_dict = getattr(msg, "model_dump", lambda: {})()
            if isinstance(msg_dict, dict):
                reasoning_content = msg_dict.get("reasoning_content")

        # Parse tool calls
        tool_calls = None
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": args},
                })

        usage = None
        if raw.usage:
            usage = {
                "prompt_tokens": raw.usage.prompt_tokens,
                "completion_tokens": raw.usage.completion_tokens,
                "total_tokens": raw.usage.total_tokens,
            }
            # DeepSeek-R1 reports reasoning_tokens separately
            if hasattr(raw.usage, "completion_tokens_details"):
                details = raw.usage.completion_tokens_details
                if details and hasattr(details, "reasoning_tokens"):
                    usage["reasoning_tokens"] = details.reasoning_tokens

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            usage=usage,
            model=raw.model,
            finish_reason=choice.finish_reason,
            reasoning_content=reasoning_content,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        openai_messages = self._to_openai_messages(messages)
        openai_tools = self._to_tool_specs(tools) if tools else None

        log_data(logger, DEBUG, f"DeepSeek generate({self.model})", data={
            "model": self.model, "messages": len(openai_messages),
        })

        try:
            raw = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                **kwargs,
            )
        except Exception as e:
            log_data(logger, WARNING, f"DeepSeek API error: {e}")
            raise ProviderError(f"DeepSeek API error: {e}") from e

        result = self._parse_response(raw)
        return result

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        client = self._get_client()
        openai_messages = self._to_openai_messages(messages)
        openai_tools = self._to_tool_specs(tools) if tools else None

        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs,
            )
        except Exception as e:
            raise ProviderError(f"DeepSeek API error: {e}") from e

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_call_deltas: dict[int, dict] = {}
        final_reasoning: str | None = None

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                    # Check for reasoning_tokens
                    if hasattr(chunk.usage, "completion_tokens_details"):
                        details = chunk.usage.completion_tokens_details
                        if details and hasattr(details, "reasoning_tokens"):
                            usage["reasoning_tokens"] = details.reasoning_tokens
                    yield LLMResponse(
                        content="".join(content_parts) if content_parts else None,
                        reasoning_content=final_reasoning or "".join(reasoning_parts) or None,
                        tool_calls=None,
                        usage=usage,
                        model=chunk.model,
                        finish_reason="stop",
                    )
                continue

            # Handle reasoning_content (DeepSeek-R1 specific)
            rc = getattr(delta, "reasoning_content", None)
            if rc:
                reasoning_parts.append(rc)
                final_reasoning = "".join(reasoning_parts)

            if delta.content:
                yield delta.content
                content_parts.append(delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_call_deltas[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_call_deltas[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_call_deltas[idx]["function"]["arguments"] += tc.function.arguments

            finish = chunk.choices[0].finish_reason if chunk.choices else None
            if finish:
                tc_list = None
                if tool_call_deltas:
                    tc_list = []
                    for idx in sorted(tool_call_deltas):
                        d = tool_call_deltas[idx]
                        try:
                            args = json.loads(d["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = {"_raw": d["function"]["arguments"]}
                        tc_list.append({
                            "id": d["id"],
                            "type": "function",
                            "function": {"name": d["function"]["name"], "arguments": args},
                        })

                rc_final = final_reasoning or ("".join(reasoning_parts) if reasoning_parts else None)
                yield LLMResponse(
                    content="".join(content_parts) if content_parts else None,
                    tool_calls=tc_list,
                    reasoning_content=rc_final,
                    model=chunk.model,
                    finish_reason=finish,
                )
