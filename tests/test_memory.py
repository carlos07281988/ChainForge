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
