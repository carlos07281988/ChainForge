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
"""Base types for context management — strategies for controlling context windows."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message roles with defined priority."""
    system = "system"
    tool = "tool"
    user = "user"
    assistant = "assistant"


class ContextStrategy(str, Enum):
    """Strategy for managing conversation context."""
    sliding_window = "sliding_window"  # Drop oldest messages when over budget
    compress = "compress"              # Summarize old messages
    selective = "selective"            # Keep relevant history only


class TokenBudget(BaseModel):
    """Token budget per message type.

    Args:
        max_total: Maximum total tokens (default 128000 = GPT-4o context).
        max_system: Reserved tokens for system prompt (default 4000).
        max_conversation: Reserved tokens for conversation history (default 100000).
        max_tool_results: Reserved tokens for tool outputs (default 20000).
        reserve_for_response: Minimum tokens to reserve for response (default 4000).
        warn_at: Percentage at which to warn about budget pressure (default 0.8).
    """

    max_total: int = Field(default=128000, ge=1024)
    max_system: int = Field(default=4000, ge=512)
    max_conversation: int = Field(default=100000, ge=1024)
    max_tool_results: int = Field(default=20000, ge=1024)
    reserve_for_response: int = Field(default=4000, ge=1024)
    warn_at: float = Field(default=0.8, ge=0.0, le=1.0)

    def usage_ratio(self, total: int) -> float:
        """Ratio of total to max_total."""
        return total / self.max_total if self.max_total > 0 else 0.0

    def is_over(self, total: int) -> bool:
        """Check if total exceeds max_total."""
        return total >= self.max_total

    def should_warn(self, total: int) -> bool:
        """Check if usage is at warning threshold."""
        return self.usage_ratio(total) >= self.warn_at


class ContextManager(Protocol):
    """Protocol for context management strategies.

    A ContextManager receives the current message list and returns
    a trimmed/compressed version that fits within the token budget.
    """

    name: str = "context_manager"

    async def prepare(
        self,
        messages: list,
        budget: TokenBudget | None = None,
        context: dict[str, Any] | None = None,
    ) -> list:
        """Prepare messages for LLM consumption.

        Args:
            messages: Full message history.
            budget: Token budget constraints.
            context: Optional extra context.

        Returns:
            Trimmed/compressed message list ready for LLM.
        """
        ...


def estimate_tokens(text: str) -> int:
    """Rough token estimate using character count.

    For English text ~4 chars per token. For mixed content ~2 chars.
    This is a heuristic; use tiktoken or provider tokenizer for accuracy.
    """
    if not text:
        return 0
    return max(1, len(text) // 3)


def estimate_messages_tokens(messages: list) -> int:
    """Estimate total tokens in a message list."""
    total = 0
    for msg in messages:
        if hasattr(msg, "content") and msg.content:
            total += estimate_tokens(str(msg.content))
        if hasattr(msg, "role"):
            total += 1  # Role overhead
        # Tool calls add tokens
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if hasattr(tc, "args"):
                    total += estimate_tokens(str(tc.args))
                elif hasattr(tc, "function") and hasattr(tc.function, "arguments"):
                    total += estimate_tokens(str(tc.function.arguments))
    return total
