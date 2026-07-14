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
