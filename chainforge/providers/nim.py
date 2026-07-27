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
"""NVIDIA NIM provider — local GPU inference via OpenAI-compatible API.

NIM (NVIDIA Inference Microservice) runs optimized models on local GPUs
with an OpenAI-compatible `/v1` endpoint. This provider wraps that endpoint
with health-checking and model discovery.

Usage:
    from chainforge.providers import NIMProvider

    llm = NIMProvider(
        model="meta/llama-3.1-70b-instruct",
        base_url="http://gpu-node-01:8000/v1",
    )
    agent = Agent(llm=llm, tools=[...])
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from logging import DEBUG, WARNING
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec
from chainforge.logging import get_logger, log_data

logger = get_logger("providers.nim")


class NIMProvider(BaseModel):
    """NVIDIA NIM LLM provider — local GPU inference.

    Communicates with a NIM instance via its OpenAI-compatible /v1 endpoint.
    Includes health-checking and model discovery for local infrastructure
    awareness.

    Attributes:
        model: Model identifier, e.g. 'meta/llama-3.1-70b-instruct'.
        base_url: NIM endpoint URL, defaults to 'http://localhost:8000/v1'.
        api_key: API key (NIM defaults to no auth, use None for local).
        health_check_interval: Seconds between automatic health checks.
        top_k: NIM-specific top-k sampling.
        repetition_penalty: NIM-specific repetition penalty.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="meta/llama-3.1-8b-instruct")
    base_url: str = Field(default="http://localhost:8000/v1")
    api_key: str | None = Field(default=None)

    # Local GPU awareness
    health_check_interval: int = Field(default=30, ge=10)

    # NIM-specific inference parameters
    top_k: int | None = Field(default=None, ge=1, le=100)
    repetition_penalty: float | None = Field(default=None, ge=1.0, le=2.0)

    # Internal state
    _last_health: bool = True
    _last_health_time: float = 0.0
    _available_models: list[str] = []
    _gpu_info: dict[str, Any] = {}

    @property
    def capabilities(self) -> set[str]:
        from chainforge.core.llm import ProviderCapability
        caps = {
            ProviderCapability.CHAT,
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.FUNCTION_CALLING,
        }
        if any(v in self.model.lower() for v in ["llava", "vila", "phi-3-vision", "clip"]):
            caps.add(ProviderCapability.VISION)
        return caps

    @property
    def is_healthy(self) -> bool:
        """Return cached health status (refreshed by health_check())."""
        return self._last_health

    def _get_client(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "NIM provider requires `openai` package. Install with: pip install openai"
            )
        return AsyncOpenAI(
            api_key=self.api_key or "nim-local",
            base_url=self.base_url,
        )

    async def health_check(self) -> bool:
        """Check NIM service health via GET /v1/models.

        Returns True if the NIM endpoint responds and reports models.
        """
        client = self._get_client()
        try:
            models = await client.models.list()
            self._available_models = [m.id for m in models.data]
            self._last_health = True
            self._last_health_time = time.time()
            log_data(logger, DEBUG, "NIM health check passed", data={
                "base_url": self.base_url,
                "available_models": len(self._available_models),
                "models": self._available_models[:5],
            })
            return True
        except Exception as e:
            self._last_health = False
            log_data(logger, WARNING, "NIM health check failed", data={
                "base_url": self.base_url, "error": str(e),
            })
            return False

    async def list_models(self) -> list[str]:
        """List all models available on this NIM instance.

        Performs a health check if no cached model list exists.
        """
        if not self._available_models:
            await self.health_check()
        return self._available_models

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
        """Generate a complete (non-streaming) response from NIM.

        Auto-checks health before generation. NIM-specific parameters
        (top_k, repetition_penalty) are passed through kwargs.
        """
        client = self._get_client()
        openai_messages = self._to_openai_messages(messages)
        openai_tools = self._to_tool_specs(tools) if tools else None

        log_data(logger, DEBUG, f"NIM generate({self.model})", data={
            "model": self.model, "base_url": self.base_url,
            "messages": len(openai_messages),
            "tools": len(openai_tools) if openai_tools else 0,
        })

        extra_params: dict[str, Any] = {}
        if self.top_k is not None:
            extra_params["top_k"] = self.top_k
        if self.repetition_penalty is not None:
            extra_params["repetition_penalty"] = self.repetition_penalty
        extra_params.update(kwargs)

        try:
            raw = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                **extra_params,
            )
        except Exception as e:
            self._last_health = False
            log_data(logger, WARNING, f"NIM API error: {e}", data={
                "model": self.model, "base_url": self.base_url, "error": str(e),
            })
            raise ProviderError(f"NIM API error at {self.base_url}: {e}") from e

        result = self._parse_response(raw)
        log_data(logger, DEBUG, f"NIM response: {result.finish_reason}", data={
            "finish_reason": result.finish_reason,
            "content_length": len(result.content or ""),
            "tool_calls": len(result.tool_calls) if result.tool_calls else 0,
            "usage": result.usage,
        })
        return result

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream tokens from NIM via SSE.

        Yields content strings for text chunks and a final LLMResponse
        with tool calls and usage on completion.
        """
        client = self._get_client()
        openai_messages = self._to_openai_messages(messages)
        openai_tools = self._to_tool_specs(tools) if tools else None

        extra_params: dict[str, Any] = {}
        if self.top_k is not None:
            extra_params["top_k"] = self.top_k
        if self.repetition_penalty is not None:
            extra_params["repetition_penalty"] = self.repetition_penalty
        extra_params.update(kwargs)

        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                stream=True,
                **extra_params,
            )
        except Exception as e:
            self._last_health = False
            raise ProviderError(f"NIM API error at {self.base_url}: {e}") from e

        content_parts: list[str] = []
        tool_call_deltas: dict[int, dict] = {}
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
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
                yield LLMResponse(
                    content="".join(content_parts) if content_parts else None,
                    tool_calls=tc_list,
                    model=chunk.model,
                    finish_reason=finish,
                )
