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
"""LLM abstraction — provider-agnostic interface for language models."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec


# ── Token pricing (approximate USD per 1K tokens) ────────────────────────


MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-haiku-3-5": {"input": 0.0008, "output": 0.004},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-2.0-pro": {"input": 0.002, "output": 0.005},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a model call based on token counts."""
    # Try exact model match, then prefix match
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        for prefix, p in MODEL_PRICING.items():
            if model.startswith(prefix) or prefix.startswith(model):
                pricing = p
                break
    if pricing is None:
        return 0.0
    return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]


# ── LLMResponse ──────────────────────────────────────────────────────────


class LLMResponse(BaseModel):
    """A structured response from an LLM."""

    content: str | None = Field(default=None, description="Text output")
    tool_calls: list[dict[str, Any]] | None = Field(default=None, description="Tool calls requested")
    usage: dict[str, int] | None = Field(default=None, description="Token usage info")
    model: str = Field(default="", description="Model name")
    finish_reason: str | None = Field(default=None)
    reasoning_content: str | None = Field(default=None, description="Reasoning/thinking trace (DeepSeek-R1, o-series)")
    cost: float | None = Field(default=None, description="Estimated USD cost")

    def model_post_init(self, __context):
        """Auto-calculate cost from usage if not provided."""
        if self.cost is None and self.usage and self.model:
            inp = self.usage.get("prompt_tokens", 0)
            out = self.usage.get("completion_tokens", 0)
            if inp or out:
                self.cost = estimate_cost(self.model, inp, out)


# ── Provider capability set ──────────────────────────────────────────────


class ProviderCapability:
    """Well-known provider capability identifiers.

    These are used in LLM.capabilities to declare what a provider supports.
    """
    CHAT = "chat"
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    VISION = "vision"
    STRUCTURED_OUTPUT = "structured_output"
    REASONING = "reasoning"
    FUNCTION_CALLING = "function_calling"
    PARALLEL_TOOL_CALLS = "parallel_tool_calls"


# ── LLM Protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class LLM(Protocol):
    """Protocol for any LLM provider.

    Capabilities: declare what this provider supports via the capabilities
    property (set of ProviderCapability constants).
    """

    model: str
    """Model identifier string."""

    @property
    def capabilities(self) -> set[str]:
        """Set of ProviderCapability identifiers this provider supports."""
        return {ProviderCapability.CHAT, ProviderCapability.STREAMING}

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
