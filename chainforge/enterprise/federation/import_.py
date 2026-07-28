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
"""FederatedAgent — import an external agent as a ChainForge-compatible LLM."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.core.llm import LLM, LLMResponse, ProviderCapability
from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec
from chainforge.enterprise.federation.protocol import InteropRequest, InteropResponse
from chainforge.logging import get_logger

logger = get_logger("enterprise.federation")


class FederatedAgent(BaseModel):
    """Import an external agent (any framework) as a ChainForge-compatible LLM.

    The external agent speaks the ChainForge Interop Protocol. This class
    wraps it so that ChainForge's Agent loop can treat it like any other LLM.

    Usage:
        external = FederatedAgent(
            endpoint="https://langchain-agent.internal/agent",
            protocol="chainforge-interop-v1",
        )
        agent = Agent(llm=external, tools=[...])
        # Now treat the external LangChain agent as if it were an LLM provider!
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    endpoint: str = Field(default="http://localhost:9100/agent")
    protocol: str = Field(default="chainforge-interop-v1")
    model: str = Field(default="federated-agent")
    api_key: str | None = None

    @property
    def capabilities(self) -> set[str]:
        return {
            ProviderCapability.CHAT,
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
        }

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send messages to the external agent and get a response."""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "FederatedAgent requires httpx. Install with: pip install httpx"
            )

        req = InteropRequest(
            messages=[m.model_dump_openai() for m in messages],
            tools=[
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in (tools or [])
            ],
            context=kwargs.get("context", {}),
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = await client.post(
                self.endpoint, json=req.model_dump(), headers=headers
            )
            if resp.status_code != 200:
                return LLMResponse(
                    content="",
                    model=self.model,
                    finish_reason="error",
                    cost=0.0,
                    usage={
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                )
            data = resp.json()
            iresp = InteropResponse(**data)
            return LLMResponse(
                content=iresp.content,
                tool_calls=iresp.tool_calls if iresp.tool_calls else None,
                usage=iresp.usage if iresp.usage else None,
                model=iresp.model or self.model,
                finish_reason=iresp.finish_reason,
                cost=0.0,
            )

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream from external agent (returns complete response as single chunk)."""
        result = await self.generate(messages, tools, **kwargs)
        if result.content:
            for chunk in result.content.split():
                yield chunk + " "
        yield result

    async def health_check(self) -> bool:
        """Check if the external agent is reachable."""
        try:
            import httpx

            url = self.endpoint.replace("/agent", "/health")
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False
