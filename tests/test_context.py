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
"""Tests for the context management module."""

import pytest
from chainforge.context import (
    TokenBudget,
    estimate_tokens,
    estimate_messages_tokens,
    SlidingWindowStrategy,
    CompressorStrategy,
)
from chainforge.core.message import Message, Role


class TestTokenBudget:
    def test_default_budget(self):
        b = TokenBudget()
        assert b.max_total == 128000
        assert b.max_system == 4000

    def test_usage_ratio(self):
        b = TokenBudget(max_total=1024)
        assert b.usage_ratio(512) == 0.5
        assert b.usage_ratio(1024) == 1.0

    def test_is_over(self):
        b = TokenBudget(max_total=1024)
        assert b.is_over(1025) is True
        assert b.is_over(1023) is False

    def test_should_warn(self):
        b = TokenBudget(max_total=1024, warn_at=0.8)
        assert b.should_warn(820) is True
        assert b.should_warn(700) is False

    def test_custom_budget(self):
        b = TokenBudget(max_total=32000, max_conversation=24000, reserve_for_response=2000)
        assert b.max_total == 32000
        assert b.max_conversation == 24000


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_simple_text(self):
        assert estimate_tokens("hello world") == 3  # 11 chars / 4 = 2.75 -> 3

    def test_long_text(self):
        text = "word " * 100  # ~500 chars
        assert estimate_tokens(text) > 0

    def test_estimate_messages(self):
        msgs = [
            Message(role=Role.user, content="Hello"),
            Message(role=Role.assistant, content="Hi there!"),
        ]
        tokens = estimate_messages_tokens(msgs)
        assert tokens > 0

    def test_estimate_messages_empty(self):
        assert estimate_messages_tokens([]) == 0

    def test_estimate_messages_with_tool_calls(self):
        from chainforge.core.message import ToolCall
        msg = Message(role=Role.assistant, content="Let me check", tool_calls=[
            ToolCall(id="1", name="calc", args={"x": 1})
        ])
        tokens = estimate_messages_tokens([msg])
        assert tokens > 5


class TestSlidingWindowStrategy:
    @pytest.mark.asyncio
    async def test_returns_same_if_under_budget(self):
        strategy = SlidingWindowStrategy(keep_last=5)
        msgs = [
            Message(role=Role.system, content="You are helpful."),
            Message(role=Role.user, content="Hi"),
            Message(role=Role.assistant, content="Hello!"),
        ]
        result = await strategy.prepare(msgs)
        assert len(result) == len(msgs)

    @pytest.mark.asyncio
    async def test_preserves_system_messages(self):
        strategy = SlidingWindowStrategy(keep_last=2)
        msgs = [
            Message(role=Role.system, content="System prompt"),
            Message(role=Role.user, content="M1"),
            Message(role=Role.assistant, content="A1"),
            Message(role=Role.user, content="M2"),
            Message(role=Role.assistant, content="A2"),
            Message(role=Role.user, content="M3"),
            Message(role=Role.assistant, content="A3"),
        ]
        result = await strategy.prepare(msgs)
        # System prompt should be preserved
        assert any(getattr(m, "role", "") == "system" for m in result)
        # Should have at most keep_last + system messages
        assert len(result) <= 3  # 1 system + 2 kept

    @pytest.mark.asyncio
    async def test_keep_last(self):
        strategy = SlidingWindowStrategy(keep_last=3)
        msgs = [
            Message(role=Role.user, content=f"Message {i}")
            for i in range(10)
        ]
        result = await strategy.prepare(msgs)
        assert len(result) <= 3

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        strategy = SlidingWindowStrategy()
        result = await strategy.prepare([])
        assert result == []

    @pytest.mark.asyncio
    async def test_drop_tools_first(self):
        strategy = SlidingWindowStrategy(keep_last=2, drop_tools_first=True)
        msgs = [
            Message(role=Role.system, content="System"),
            Message(role=Role.user, content="Hi"),
            Message(role=Role.assistant, content="Hello"),
            Message(role=Role.tool, content="tool_result_1"),
            Message(role=Role.tool, content="tool_result_2"),
            Message(role=Role.tool, content="tool_result_3"),
        ]
        result = await strategy.prepare(msgs)
        # System + 2 recent conversation messages should be preserved
        system_count = sum(1 for m in result if getattr(m, "role", "") == "system")
        assert system_count == 1


class TestCompressorStrategy:
    @pytest.mark.asyncio
    async def test_returns_same_if_under_budget(self):
        strategy = CompressorStrategy(compress_after=20)
        msgs = [
            Message(role=Role.user, content="Short conversation"),
            Message(role=Role.assistant, content="With just a few turns"),
        ]
        result = await strategy.prepare(msgs)
        assert len(result) == len(msgs)

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        strategy = CompressorStrategy()
        result = await strategy.prepare([])
        assert result == []

    @pytest.mark.asyncio
    async def test_always_keeps_recent(self):
        strategy = CompressorStrategy(compress_after=3, always_keep_recent=2)
        msgs = [
            Message(role=Role.system, content="System prompt"),
            Message(role=Role.user, content="Old message 1"),
            Message(role=Role.assistant, content="Old reply 1"),
            Message(role=Role.user, content="Old message 2"),
            Message(role=Role.assistant, content="Old reply 2"),
            Message(role=Role.user, content="Recent message 1"),
            Message(role=Role.assistant, content="Recent reply 1"),
        ]
        result = await strategy.prepare(msgs)
        # System should be preserved
        assert any(getattr(m, "role", "") == "system" for m in result)
        # Should be compressed (system + summary + recent)
        assert len(result) < len(msgs)

    @pytest.mark.asyncio
    async def test_simple_summary_fallback(self):
        strategy = CompressorStrategy(compress_after=2, always_keep_recent=1)
        msgs = [
            Message(role=Role.user, content="What is Python?"),
            Message(role=Role.assistant, content="Python is a programming language."),
            Message(role=Role.user, content="Tell me more."),
        ]
        result = await strategy.prepare(msgs)
        # Should produce a summary even without LLM
        assert len(result) > 0
        assert len(result) < len(msgs)

    @pytest.mark.asyncio
    async def test_not_enough_messages(self):
        strategy = CompressorStrategy(compress_after=50)
        msgs = [Message(role=Role.user, content="Just one message")]
        result = await strategy.prepare(msgs)
        assert len(result) == 1
