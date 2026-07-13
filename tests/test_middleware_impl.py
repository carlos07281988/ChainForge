"""Tests for middleware implementations (retry, rate_limit, timeout)."""

from collections.abc import AsyncIterator

import pytest

from chainforge.core.message import Message
from chainforge.core.middleware import MiddlewareChain
from chainforge.core.stream import StreamEvent
from chainforge.middleware import retry_middleware, rate_limit_middleware, timeout_middleware


async def _final_handler(messages, ctx) -> AsyncIterator[StreamEvent]:
    yield StreamEvent.text("success")
    yield StreamEvent.done()


class TestRetryMiddleware:
    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        mw = retry_middleware(max_retries=2)
        chain = MiddlewareChain([mw])
        events = []
        async for event in chain.run([], {}, _final_handler):
            events.append(event)
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        call_count = 0

        async def _failing_handler(messages, ctx) -> AsyncIterator[StreamEvent]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient error")
            yield StreamEvent.text("finally OK")
            yield StreamEvent.done()

        mw = retry_middleware(max_retries=3, base_delay=0.01)
        chain = MiddlewareChain([mw])
        events = []
        async for event in chain.run([], {}, _failing_handler):
            events.append(event)
        assert any(e.type.value == "text" for e in events)
        assert call_count == 3


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_rate_limit_high_limit(self):
        mw = rate_limit_middleware(calls_per_minute=10000)
        chain = MiddlewareChain([mw])
        events = []
        async for event in chain.run([], {}, _final_handler):
            events.append(event)
        assert len(events) == 2


class TestTimeoutMiddleware:
    @pytest.mark.asyncio
    async def test_timeout_no_timeout(self):
        mw = timeout_middleware(timeout_seconds=60)
        chain = MiddlewareChain([mw])
        events = []
        async for event in chain.run([], {}, _final_handler):
            events.append(event)
        assert len(events) == 2
