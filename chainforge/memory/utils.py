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
"""Memory utility functions — message trimming and summarization."""

from __future__ import annotations

from typing import Any

from chainforge.core.llm import LLM
from chainforge.core.message import Message, Role
from chainforge.logging import get_logger

logger = get_logger("memory.utils")

SUMMARY_SYSTEM_PROMPT = """Summarize the following conversation, keeping:
1. Key facts and decisions made
2. User preferences and personal information
3. Task progress and next steps
4. Important context for continuing

Be concise but preserve all important details."""


async def trim_messages(
    messages: list[Message],
    max_messages: int = 20,
    strategy: str = "sliding_window",
) -> list[Message]:
    """Trim a message list to fit within constraints.

    Args:
        messages: Full message history.
        max_messages: Maximum number of messages to keep.
        strategy: Trimming strategy:
            - "sliding_window": Keep the most recent N messages (default).
            - "drop_system": Keep system message + most recent N-1 messages.
            - "drop_old_alternating": Keep system + recent, prefer assistant responses.

    Returns:
        Trimmed message list.
    """
    if len(messages) <= max_messages:
        return list(messages)

    if strategy == "sliding_window":
        return messages[-max_messages:]

    if strategy == "drop_system":
        system_msgs = [m for m in messages if m.role == Role.system]
        other_msgs = [m for m in messages if m.role != Role.system]
        kept_other = other_msgs[-(max_messages - len(system_msgs)):]
        return system_msgs + kept_other

    if strategy == "drop_old_alternating":
        system_msgs = [m for m in messages if m.role == Role.system]
        non_system = [m for m in messages if m.role != Role.system]
        # Keep most recent, preferring assistant messages
        kept = non_system[-(max_messages - len(system_msgs)):]
        return system_msgs + kept

    return messages[-max_messages:]


async def summarize_messages(
    messages: list[Message],
    llm: LLM,
    max_messages: int = 20,
) -> list[Message]:
    """Summarize messages when they exceed the limit.

    For old messages beyond the limit, generates a summary using the LLM.
    Keeps recent messages intact and prepends a summary system message.

    Args:
        messages: Full message history.
        llm: LLM instance for generating summaries.
        max_messages: Keep this many most recent messages intact.

    Returns:
        List with [Summary, top N recent messages].
    """
    if len(messages) <= max_messages:
        return list(messages)

    # Split into "to be summarized" and "keep as-is"
    to_summarize = messages[:-max_messages]
    recent = messages[-max_messages:]

    # Build summary text
    summary_text = "\n".join(
        f"[{m.role.value}] {m.content or '(tool call)'}" for m in to_summarize if m.content
    )

    try:
        resp = await llm.generate([
            Message.system(SUMMARY_SYSTEM_PROMPT),
            Message.user(f"Summarize this conversation:\n\n{summary_text}"),
        ])
        summary_content = resp.content or "(summary unavailable)"
        logger.debug(f"Generated summary ({len(summary_content)} chars)")
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")
        summary_content = f"(summary of {len(to_summarize)} earlier messages)"

    return [
        Message.system(f"Conversation summary: {summary_content}"),
        *recent,
    ]


async def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Estimate token count for a text string.

    Rough estimation: ~4 chars per token for English text.
    For production, use a proper tokenizer (tiktoken).
    """
    return len(text) // 4 + 1


async def total_message_tokens(messages: list[Message], model: str = "gpt-4o") -> int:
    """Estimate total tokens across a message list."""
    total = 0
    for m in messages:
        if m.content:
            total += await count_tokens(m.content, model)
        if m.tool_calls:
            for tc in m.tool_calls:
                total += await count_tokens(tc.name + str(tc.args))
    return total
