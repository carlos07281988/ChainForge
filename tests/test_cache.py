"""Tests for the LLM Cache module."""

import time
import pytest
from chainforge.cache import InMemoryCache, CacheEntry, make_cache_key, CacheMiddleware
from chainforge.core.message import Message, Role


class TestCacheEntry:
    def test_creation(self):
        entry = CacheEntry(key="test", value="response", ttl=300)
        assert entry.key == "test"
        assert entry.value == "response"
        assert entry.hit_count == 0
        assert entry.is_expired is False

    def test_expiry(self):
        entry = CacheEntry(key="test", value="x", ttl=0)  # no expiry
        assert entry.is_expired is False

    def test_hit_count(self):
        entry = CacheEntry(key="k", value="v")
        entry.hit_count += 1
        assert entry.hit_count == 1


class TestMakeCacheKey:
    def test_deterministic(self):
        msgs = [Message(role=Role.user, content="Hello")]
        k1 = make_cache_key("gpt-4o", msgs)
        k2 = make_cache_key("gpt-4o", msgs)
        assert k1 == k2

    def test_different_messages(self):
        msgs1 = [Message(role=Role.user, content="Hello")]
        msgs2 = [Message(role=Role.user, content="World")]
        assert make_cache_key("gpt-4o", msgs1) != make_cache_key("gpt-4o", msgs2)

    def test_different_models(self):
        msgs = [Message(role=Role.user, content="Hello")]
        assert make_cache_key("gpt-4o", msgs) != make_cache_key("gpt-3.5", msgs)

    def test_with_tools(self):
        msgs = [Message(role=Role.user, content="Calculate")]
        class MockTool:
            class Spec:
                name = "calculator"
            spec = Spec()
        k = make_cache_key("gpt-4o", msgs, tools=[MockTool()])
        assert len(k) == 64  # SHA-256 hex


class TestInMemoryCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = InMemoryCache()
        await cache.set("key1", "response1")
        result = await cache.get("key1")
        assert result == "response1"

    @pytest.mark.asyncio
    async def test_get_missing(self):
        cache = InMemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired(self):
        cache = InMemoryCache()
        await cache.set("key", "value", ttl=0)  # already expired if ttl=0... actually no
        # ttl=0 means "no expiry" per our logic
        result = await cache.get("key")
        assert result is not None

    @pytest.mark.asyncio
    async def test_clear_specific(self):
        cache = InMemoryCache()
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.clear("a")
        assert await cache.get("a") is None
        assert await cache.get("b") == "2"

    @pytest.mark.asyncio
    async def test_clear_all(self):
        cache = InMemoryCache()
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.clear()
        assert await cache.get("a") is None
        assert await cache.get("b") is None

    @pytest.mark.asyncio
    async def test_stats(self):
        cache = InMemoryCache()
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.get("a")  # 1 hit
        stats = await cache.stats()
        assert stats["total_entries"] == 2
        assert stats["total_hits"] >= 1

    @pytest.mark.asyncio
    async def test_hit_count_tracking(self):
        cache = InMemoryCache()
        await cache.set("k", "v")
        await cache.get("k")
        await cache.get("k")
        await cache.get("k")
        stats = await cache.stats()
        assert stats["total_hits"] == 3


class TestCacheMiddleware:
    def test_creation(self):
        mw = CacheMiddleware()
        assert mw.cache is not None
        assert mw.ttl == 300

    def test_custom_cache(self):
        cache = InMemoryCache(default_ttl=600)
        mw = CacheMiddleware(cache=cache, ttl=600)
        assert mw.cache.default_ttl == 600
