"""Context compressor — summarize old messages to reclaim token budget."""

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

logger = get_logger("context.compressor")

import logging


class CompressorStrategy:
    """LLM-based context compression — summarizes older conversation turns.

    Uses an LLM call to compress a block of messages into a concise summary,
    preserving key facts, decisions, and user preferences.

    Args:
        llm: An LLM provider with a ``generate()`` method.
        max_compress_tokens: Max tokens for each compressed block (default 1024).
        compress_after: Number of messages before triggering compression (default 20).
        always_keep_recent: Always keep last N messages uncompressed (default 6).
    """

    name: str = "compressor"

    def __init__(
        self,
        llm: Any = None,
        max_compress_tokens: int = 1024,
        compress_after: int = 20,
        always_keep_recent: int = 6,
    ):
        self._llm = llm
        self.max_compress_tokens = max_compress_tokens
        self.compress_after = compress_after
        self.always_keep_recent = always_keep_recent

    async def prepare(
        self,
        messages: list,
        budget: TokenBudget | None = None,
        context: dict[str, Any] | None = None,
    ) -> list:
        if not messages:
            return messages

        total_tokens = estimate_messages_tokens(messages)
        budget = budget or TokenBudget()

        # Compress if over budget or enough messages accumulated
        should_compress = budget.is_over(total_tokens) or len(messages) >= self.compress_after
        if not should_compress:
            return messages

        # Separate system, recent conversation, and compressible messages
        system_msgs = []
        recent = []
        compressible = []

        for msg in messages:
            role = getattr(msg, "role", "")
            if role == MessageRole.system:
                system_msgs.append(msg)
            else:
                compressible.append(msg)

        # Keep recent messages uncompressed
        if len(compressible) > self.always_keep_recent:
            recent = compressible[-self.always_keep_recent:]
            compressible = compressible[:-self.always_keep_recent]

        if not compressible:
            return messages

        # Compress the old messages into a summary
        summary = await self._summarize(compressible)

        # Build the compressed message list
        from chainforge.core.message import Message

        compressed = list(system_msgs)
        if summary:
            compressed.append(Message(role=MessageRole.system, content=f"[Context Summary]\n{summary}"))
        compressed.extend(recent)

        final_tokens = estimate_messages_tokens(compressed)
        log_data(logger, logging.INFO, f"Compressor: {total_tokens} → {final_tokens} tokens ({len(messages)} → {len(compressed)} msgs)",
                 data={"before_tokens": total_tokens, "after_tokens": final_tokens, "summary_len": len(summary or "")})
        return compressed

    async def _summarize(self, messages: list) -> str:
        """Summarize a list of messages into a concise string."""
        if not messages:
            return ""

        # Build a summary prompt
        conversation_text = []
        for m in messages:
            role = getattr(m, "role", "unknown")
            content = str(getattr(m, "content", ""))[:500]
            conversation_text.append(f"[{role}]: {content}")

        summary_prompt = (
            "Summarize the following conversation turn concisely. "
            "Preserve: user preferences, decisions made, facts established, "
            "and any action results that may be needed later.\n\n"
            + "\n".join(conversation_text[-20:])  # Last 20 messages max
        )

        if self._llm:
            try:
                from chainforge.core.message import Message
                response = await self._llm.generate(
                    [Message(role=MessageRole.user, content=summary_prompt)],
                    max_tokens=self.max_compress_tokens,
                )
                return response.content or ""
            except Exception as e:
                logger.warning(f"Compression LLM call failed: {e}")
                return self._simple_summary(messages)
        else:
            return self._simple_summary(messages)

    def _simple_summary(self, messages: list) -> str:
        """Simple heuristic-based summarization (no LLM needed)."""
        parts = []
        for m in messages[-10:]:  # Only last 10
            role = getattr(m, "role", "?")
            content = str(getattr(m, "content", ""))[:200]
            if content.strip():
                parts.append(f"[{role}] {content.strip()}")
        return "\n".join(parts) if parts else ""
