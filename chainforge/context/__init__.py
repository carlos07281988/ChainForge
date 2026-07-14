"""Context Management — control and optimize Agent context windows.

Strategies:
  - SlidingWindowStrategy: token-aware truncation, keeps recent messages
  - CompressorStrategy: LLM-based summarization of old messages
  - TokenBudget: per-message-type token allocation

Usage:
    from chainforge.context import SlidingWindowStrategy, TokenBudget

    strategy = SlidingWindowStrategy(keep_last=15)
    budget = TokenBudget(max_total=128000)

    trimmed = await strategy.prepare(messages, budget)
"""

from chainforge.context.base import (
    ContextManager,
    ContextStrategy,
    MessageRole,
    TokenBudget,
    estimate_tokens,
    estimate_messages_tokens,
)
from chainforge.context.sliding_window import SlidingWindowStrategy
from chainforge.context.compressor import CompressorStrategy

__all__ = [
    "ContextManager",
    "ContextStrategy",
    "MessageRole",
    "TokenBudget",
    "estimate_tokens",
    "estimate_messages_tokens",
    "SlidingWindowStrategy",
    "CompressorStrategy",
]
