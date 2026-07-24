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
"""Tests for AdaptiveRouter (SmartRouter 2.0)."""

import asyncio

import pytest

from chainforge.routing.adaptive import (
    AdaptiveRouter,
    CostTracker,
    ModelInfo,
    ModelRegistry,
)


# ── Test ModelRegistry ─────────────────────────────────────────────────────


class TestModelRegistry:
    def test_register_and_get(self):
        r = ModelRegistry()
        info = r.register("gpt-4o", cost_per_1k=0.01, latency_ms=500,
                          capabilities={"chat", "tool_calling"})
        assert info.name == "gpt-4o"
        assert r.get("gpt-4o") is info
        assert r.get("nonexistent") is None

    def test_count(self):
        r = ModelRegistry()
        assert r.count == 0
        r.register("a")
        r.register("b")
        assert r.count == 2

    def test_all(self):
        r = ModelRegistry()
        r.register("a")
        r.register("b")
        assert len(r.all) == 2

    def test_query_by_capability(self):
        r = ModelRegistry()
        r.register("mini", capabilities={"chat"})
        r.register("full", capabilities={"chat", "vision"})
        results = r.query(capability="vision")
        assert len(results) == 1
        assert results[0].name == "full"

    def test_query_by_max_cost(self):
        r = ModelRegistry()
        r.register("cheap", cost_per_1k=0.001)
        r.register("expensive", cost_per_1k=0.01)
        results = r.query(max_cost=0.005)
        assert len(results) == 1
        assert results[0].name == "cheap"

    def test_cheapest(self):
        r = ModelRegistry()
        r.register("a", cost_per_1k=0.01)
        r.register("b", cost_per_1k=0.001, capabilities={"chat"})
        c = r.cheapest(capability="chat")
        assert c is not None
        assert c.name == "b"

    def test_most_capable(self):
        r = ModelRegistry()
        r.register("a", capabilities={"chat"})
        r.register("b", capabilities={"chat", "vision", "reasoning"})
        m = r.most_capable()
        assert m is not None
        assert m.name == "b"

    def test_remove(self):
        r = ModelRegistry()
        r.register("test")
        assert r.remove("test") is True
        assert r.remove("test") is False

    def test_default_capabilities(self):
        r = ModelRegistry()
        info = r.register("basic")
        assert "chat" in info.capabilities


# ── Test CostTracker ──────────────────────────────────────────────────────


class TestCostTracker:
    def test_track_call(self):
        t = CostTracker()
        t.track_call("gpt-4o", tokens=1000, duration_ms=500)
        assert t.total_calls == 1
        assert t.total_cost > 0

    def test_track_multiple_models(self):
        t = CostTracker()
        t.track_call("gpt-4o", tokens=500)
        t.track_call("gpt-4o-mini", tokens=200)
        assert t.total_calls == 2

    def test_model_stats(self):
        t = CostTracker()
        t.track_call("gpt-4o", tokens=1000, duration_ms=500)
        stats = t.model_stats("gpt-4o")
        assert stats["calls"] == 1
        assert stats["total_tokens"] == 1000
        assert stats["avg_latency_ms"] > 0

    def test_model_stats_empty(self):
        t = CostTracker()
        stats = t.model_stats("nonexistent")
        assert stats["calls"] == 0

    def test_summary(self):
        t = CostTracker()
        t.track_call("gpt-4o", tokens=1000)
        s = t.summary()
        assert s["total_calls"] == 1
        assert "gpt-4o" in s["per_model"]

    def test_reset(self):
        t = CostTracker()
        t.track_call("gpt-4o", tokens=500)
        t.reset()
        assert t.total_calls == 0
        assert t.total_cost == 0.0


# ── Test AdaptiveRouter ───────────────────────────────────────────────────


class TestAdaptiveRouter:
    def test_create(self):
        registry = ModelRegistry()
        registry.register("gpt-4o-mini", cost_per_1k=0.001)
        registry.register("gpt-4o", cost_per_1k=0.01)
        router = AdaptiveRouter(registry=registry)
        assert router.registry.count == 2
        assert router.cost_tracker.total_calls == 0

    def test_select_cheapest_no_capability(self):
        registry = ModelRegistry()
        registry.register("gpt-4o-mini", cost_per_1k=0.001)
        registry.register("gpt-4o", cost_per_1k=0.01)
        router = AdaptiveRouter(registry=registry)
        provider = router.select_cheapest()
        assert provider is not None

    def test_select_cheapest_by_capability(self):
        registry = ModelRegistry()
        registry.register("gpt-4o-mini", cost_per_1k=0.001, capabilities={"chat"})
        registry.register("gpt-4o", cost_per_1k=0.01, capabilities={"chat", "vision"})
        router = AdaptiveRouter(registry=registry)
        provider = router.select_cheapest(capability="vision")
        assert provider is not None

    def test_select_most_capable(self):
        registry = ModelRegistry()
        registry.register("mini", capabilities={"chat"})
        registry.register("full", capabilities={"chat", "reasoning", "vision"})
        router = AdaptiveRouter(registry=registry)
        provider = router.select_most_capable()
        assert provider is not None

    def test_fallback_chain(self):
        registry = ModelRegistry()
        registry.register("mini", cost_per_1k=0.001, capabilities={"chat"})
        registry.register("full", cost_per_1k=0.01, capabilities={"chat", "reasoning"})
        router = AdaptiveRouter(registry=registry)

        chain = asyncio.run(router.fallback_chain("test"))
        assert len(chain) >= 2

    def test_stats(self):
        registry = ModelRegistry()
        registry.register("a", cost_per_1k=0.001)
        router = AdaptiveRouter(registry=registry)
        stats = router.stats()
        assert stats["registry_count"] == 1
        assert "cost_tracker" in stats
        assert stats["optimize_for"] == "cost"

    def test_optimize_for_latency(self):
        registry = ModelRegistry()
        registry.register("slow", cost_per_1k=0.001, latency_ms=2000)
        registry.register("fast", cost_per_1k=0.01, latency_ms=100)
        router = AdaptiveRouter(registry=registry, optimize_for="latency")
        provider = asyncio.run(router.select("test"))
        assert provider is not None

    def test_no_match_returns_none(self):
        registry = ModelRegistry()
        registry.register("mini", capabilities={"chat"})
        router = AdaptiveRouter(registry=registry)
        provider = asyncio.run(router.select("test", capabilities_needed={"vision"}))
        assert provider is None
