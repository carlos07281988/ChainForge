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
"""Tests for the middleware module."""

from collections.abc import AsyncIterator

import pytest

from chainforge.core.message import Message
from chainforge.core.middleware import Middleware, MiddlewareChain
from chainforge.core.stream import StreamEvent


async def _final_handler(
    messages: list[Message], ctx: dict
) -> AsyncIterator[StreamEvent]:
    yield StreamEvent.text("final output")
    yield StreamEvent.done()


async def _logging_middleware(messages, ctx, next_handler):
    yield StreamEvent.status("before")
    async for event in next_handler(messages, ctx):
        yield event
    yield StreamEvent.status("after")


class TestMiddleware:
    @pytest.mark.asyncio
    async def test_middleware_wraps_handler(self):
        chain = MiddlewareChain([_logging_middleware])
        events = []
        async for event in chain.run([], {}, _final_handler):
            events.append(event)
        assert len(events) == 4
        assert events[0].type.value == "status"
        assert events[0].content == "before"
        assert events[1].type.value == "text"
        assert events[-1].type.value == "status"

    @pytest.mark.asyncio
    async def test_no_middleware(self):
        chain = MiddlewareChain([])
        events = []
        async for event in chain.run([], {}, _final_handler):
            events.append(event)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_multiple_middlewares(self):
        async def mw1(msgs, ctx, next_fn):
            yield StreamEvent.status("mw1_start")
            async for e in next_fn(msgs, ctx):
                yield e
            yield StreamEvent.status("mw1_end")

        async def mw2(msgs, ctx, next_fn):
            yield StreamEvent.status("mw2_start")
            async for e in next_fn(msgs, ctx):
                yield e
            yield StreamEvent.status("mw2_end")

        chain = MiddlewareChain([mw1, mw2])
        events = []
        async for event in chain.run([], {}, _final_handler):
            events.append(event)
        # mw1_start, mw2_start, text, done, mw2_end, mw1_end
        assert len(events) == 6
        assert events[0].content == "mw1_start"
        assert events[1].content == "mw2_start"
        assert events[-2].content == "mw2_end"
        assert events[-1].content == "mw1_end"

    def test_middleware_name(self):
        mw = Middleware(_logging_middleware)
        assert mw.name == "_logging_middleware"
