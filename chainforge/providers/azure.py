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
"""Azure OpenAI provider — wraps Azure OpenAI API into ChainForge's LLM protocol.

Reuses OpenAI provider internals with Azure-specific configuration.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec


class AzureProvider(BaseModel):
    """Azure OpenAI LLM provider.

    Usage:
        llm = AzureProvider(
            model="gpt-4o",  # deployment name
            api_key="...",
            azure_endpoint="https://your-resource.openai.azure.com",
            api_version="2024-08-01-preview",
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="gpt-4o", description="Deployment name")
    api_key: str | None = Field(default=None)
    azure_endpoint: str | None = Field(default=None)
    api_version: str = Field(default="2024-10-01-preview")

    def _get_client(self):
        try:
            from openai import AsyncAzureOpenAI
        except ImportError:
            raise ImportError(
                "Azure provider requires `openai>=1.40`. Install with: pip install 'chainforge[azure]'"
            )
        return AsyncAzureOpenAI(
            api_key=self.api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_endpoint=self.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            api_version=self.api_version,
        )

    def _to_openai_messages(self, messages: list[Message]) -> list[dict]:
        return [m.model_dump_openai() for m in messages]

    def _to_tool_specs(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def _parse_response(self, raw: Any) -> LLMResponse:
        choice = raw.choices[0]
        msg = choice.message
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
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            usage=usage,
            model=raw.model,
            finish_reason=choice.finish_reason,
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
        try:
            raw = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                **kwargs,
            )
        except Exception as e:
            raise ProviderError(f"Azure OpenAI API error: {e}") from e
        return self._parse_response(raw)

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
            raise ProviderError(f"Azure OpenAI API error: {e}") from e

        content_parts = []
        tool_call_deltas: dict[int, dict] = {}
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                    yield LLMResponse(content="".join(content_parts) if content_parts else None, usage=usage)
                continue
            if delta.content:
                yield delta.content
                content_parts.append(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {"id": tc.id or "", "function": {"name": "", "arguments": ""}}
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
                yield LLMResponse(content="".join(content_parts) if content_parts else None, tool_calls=tc_list)
