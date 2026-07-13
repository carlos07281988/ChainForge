"""Tests for the memory module."""

import pytest

from chainforge.core.message import Message
from chainforge.memory import BufferMemory, SummaryMemory


class TestBufferMemory:
    @pytest.mark.asyncio
    async def test_add_and_load(self):
        memory = BufferMemory(max_messages=5)
        await memory.save([Message.user("Hello")])
        history = await memory.load()
        assert len(history) == 1
        assert history[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_max_messages(self):
        memory = BufferMemory(max_messages=3)
        for i in range(5):
            await memory.save([Message.user(f"msg_{i}")])
        history = await memory.load()
        assert len(history) == 3
        assert history[0].content == "msg_2"
        assert history[-1].content == "msg_4"

    @pytest.mark.asyncio
    async def test_clear(self):
        memory = BufferMemory()
        await memory.save([Message.user("Hello")])
        memory.clear()
        history = await memory.load()
        assert len(history) == 0


class TestSummaryMemory:
    @pytest.mark.asyncio
    async def test_initial_empty(self):
        memory = SummaryMemory()
        history = await memory.load()
        assert len(history) == 1
        assert "No prior conversation" in (history[0].content or "")

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        memory = SummaryMemory(max_recent=3)
        await memory.save([Message.user("Hello")])
        history = await memory.load()
        assert len(history) == 2  # summary msg + user msg
        assert history[-1].content == "Hello"
