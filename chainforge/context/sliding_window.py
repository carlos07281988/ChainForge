# Copyright 2024 ChainForge Contributors
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
"""Sliding window context strategy — keeps recent messages, drops oldest."""

from __future__ import annotations

from typing import Any

from chainforge.context.base import (
    ContextManager,
    MessageRole,
    TokenBudget,
    estimate_tokens,
    estimate_messages_tokens,
)
from chainforge.logging import get_logger, log_data

logger = get_logger("context.sliding_window")

import logging


class SlidingWindowStrategy:
    """Token-aware sliding window that preserves system prompt and recent messages.

    Strategy:
      1. Always keep system prompts.
      2. Keep recent conversation messages (last N).
      3. Drop tool results earliest when over budget.
      4. Drop older conversation messages next.

    Args:
        keep_last: Minimum conversation turns to keep (default 10).
        preserve_system: Always keep system messages (default True).
        drop_tools_first: Drop tool results before conversation (default True).
    """

    name: str = "sliding_window"

    def __init__(
        self,
        keep_last: int = 10,
        preserve_system: bool = True,
        drop_tools_first: bool = True,
    ):
        self.keep_last = keep_last
        self.preserve_system = preserve_system
        self.drop_tools_first = drop_tools_first

    async def prepare(
        self,
        messages: list,
        budget: TokenBudget | None = None,
        context: dict[str, Any] | None = None,
    ) -> list:
        if not messages:
            return messages

        budget = budget or TokenBudget()
        total_tokens = estimate_messages_tokens(messages)

        # If already under budget and enough messages kept, return as-is
        if not budget.is_over(total_tokens) and len(messages) <= self.keep_last * 2:
            return messages

        budget_target = budget.max_total - budget.reserve_for_response

        # Separate system messages from conversation
        system_msgs = []
        conversation = []
        for msg in messages:
            role = getattr(msg, "role", "")
            if self.preserve_system and role == MessageRole.system:
                system_msgs.append(msg)
            else:
                conversation.append(msg)

        # Count system tokens
        sys_tokens = estimate_messages_tokens(system_msgs)

        # Strategy: keep last N conversation messages, drop tool results first
        result = list(system_msgs)

        if self.drop_tools_first:
            # Separate tool results from user/assistant messages
            tool_msgs = [m for m in conversation if getattr(m, "role", "") == MessageRole.tool]
            kept_msgs = [m for m in conversation if getattr(m, "role", "") != MessageRole.tool]

            # Keep at least keep_last non-tool messages
            if len(kept_msgs) > self.keep_last:
                kept_msgs = kept_msgs[-self.keep_last:]

            # Add tool messages up to budget
            for tm in tool_msgs:
                current_tokens = estimate_messages_tokens(result + kept_msgs + [tm])
                if current_tokens + sys_tokens < budget_target:
                    kept_msgs.append(tm)

            result.extend(kept_msgs)
        else:
            # Simple: keep last N messages
            keep = conversation[-self.keep_last:] if len(conversation) > self.keep_last else conversation
            result.extend(keep)

        final_tokens = estimate_messages_tokens(result)
        log_data(logger, logging.INFO, f"Sliding window: {total_tokens} → {final_tokens} tokens, {len(messages)} → {len(result)} messages",
                 data={"before_tokens": total_tokens, "after_tokens": final_tokens, "before_msgs": len(messages), "after_msgs": len(result)})

        return result
