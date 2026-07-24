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
"""AdaptiveRouter — SmartRouter 2.0 with capability, cost, and latency optimization.

Extends the base SmartRouter with:
  - ModelRegistry: declare per-model capabilities, costs, latency
  - CostTracker: accumulate cost/latency metrics per model
  - Adaptive selection: best model for each task based on capability + cost + latency
  - Fallback chains: try model A, fall back to B, C on failure

Usage:
    from chainforge.routing.adaptive import AdaptiveRouter, ModelRegistry, CostTracker

    registry = ModelRegistry()
    registry.register("gpt-4o-mini", cost_per_1k=0.00015, latency_ms=300,
                      capabilities={"chat", "tool_calling"})
    registry.register("gpt-4o", cost_per_1k=0.0025, latency_ms=800,
                      capabilities={"chat", "tool_calling", "vision", "reasoning"})
    registry.register("claude-sonnet", cost_per_1k=0.003, latency_ms=1000,
                      capabilities={"chat", "tool_calling", "reasoning"})

    router = AdaptiveRouter(registry=registry, optimize_for="cost")
    provider = await router.select("What is 2+2?")
    # → gpt-4o-mini

    provider = await router.select("Write a complex algorithm")
    # → gpt-4o or claude-sonnet (needs reasoning)
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("routing.adaptive")

_DEFAULT_CAPABILITIES: set[str] = {"chat"}


# ── ModelRegistry ─────────────────────────────────────────────────────────


class ModelInfo(BaseModel):
    """Information about a registered model."""

    name: str = Field(description="Model identifier")
    cost_per_1k: float = Field(default=0.0, description="Cost per 1K input tokens (USD)")
    latency_ms: float = Field(default=500.0, description="Average latency in milliseconds")
    capabilities: set[str] = Field(default_factory=lambda: {"chat"},
                                    description="Model capabilities (chat, tool_calling, vision, reasoning, code)")
    provider: str = Field(default="openai", description="Provider name")


class ModelRegistry(BaseModel):
    """Registry of available models with capabilities, costs, and latency.

    Usage:
        registry = ModelRegistry()
        registry.register("gpt-4o", cost_per_1k=0.01, latency_ms=500,
                          capabilities={"chat", "tool_calling", "vision"})
        registry.register("gpt-4o-mini", cost_per_1k=0.001, latency_ms=200)

        # Query
        models = registry.query(capability="reasoning")
        cheap = registry.query(max_cost=0.002)
    """

    _models: dict[str, ModelInfo] = {}

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._models = {}

    def register(self, name: str, cost_per_1k: float = 0.0,
                 latency_ms: float = 500.0,
                 capabilities: set[str] | None = None,
                 provider: str = "openai") -> ModelInfo:
        """Register a model.

        Args:
            name: Model identifier (e.g. "gpt-4o").
            cost_per_1k: Cost per 1K input tokens in USD.
            latency_ms: Average latency in milliseconds.
            capabilities: Set of capabilities (chat, tool_calling, vision, reasoning, code).
            provider: Provider name.

        Returns:
            The registered ModelInfo.
        """
        info = ModelInfo(
            name=name,
            cost_per_1k=cost_per_1k,
            latency_ms=latency_ms,
            capabilities=capabilities or {"chat"},
            provider=provider,
        )
        self._models[name] = info
        return info

    def get(self, name: str) -> ModelInfo | None:
        return self._models.get(name)

    @property
    def all(self) -> list[ModelInfo]:
        return list(self._models.values())

    @property
    def count(self) -> int:
        return len(self._models)

    def query(self, capability: str | None = None,
              max_cost: float | None = None,
              min_capability: str | None = None) -> list[ModelInfo]:
        """Query models by capability and cost constraints.

        Args:
            capability: Required capability.
            max_cost: Max cost per 1K tokens.
            min_capability: Minimum capability to include.

        Returns:
            Matching models, sorted by cost ascending.
        """
        results = list(self._models.values())

        if capability:
            results = [m for m in results if capability in m.capabilities]
        if max_cost is not None:
            results = [m for m in results if m.cost_per_1k <= max_cost]

        results.sort(key=lambda m: m.cost_per_1k)
        return results

    def cheapest(self, capability: str | None = None) -> ModelInfo | None:
        """Get the cheapest model with the given capability."""
        models = self.query(capability=capability)
        return models[0] if models else None

    def most_capable(self) -> ModelInfo | None:
        """Get the model with the most capabilities."""
        if not self._models:
            return None
        return max(self._models.values(), key=lambda m: len(m.capabilities))

    def remove(self, name: str) -> bool:
        return self._models.pop(name, None) is not None


# ── CostTracker ────────────────────────────────────────────────────────────


class CostTracker:
    """Tracks cost and latency metrics per model.

    Usage:
        tracker = CostTracker()
        tracker.track_call("gpt-4o", tokens=500, duration_ms=800)
        tracker.track_call("gpt-4o-mini", tokens=200, duration_ms=300)

        summary = tracker.summary()
        # {"total_cost": 0.0015, "total_calls": 2, "per_model": {...}}
    """

    def __init__(self):
        self._costs: dict[str, float] = defaultdict(float)
        self._calls: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._tokens: dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def track_call(self, model_name: str, tokens: int = 0,
                   duration_ms: float = 0.0, cost: float | None = None) -> None:
        """Record a model call.

        Args:
            model_name: Model identifier.
            tokens: Tokens consumed.
            duration_ms: Call duration in milliseconds.
            cost: Explicit cost. If None, estimated from token count.
        """
        self._calls[model_name] += 1
        self._tokens[model_name] += tokens
        self._latencies[model_name].append(duration_ms)

        if cost is not None:
            self._costs[model_name] += cost
        else:
            # Rough estimate: $0.01 per 1K tokens for capable models
            estimated_cost = tokens * 0.00001
            self._costs[model_name] += estimated_cost

    @property
    def total_cost(self) -> float:
        return sum(self._costs.values())

    @property
    def total_calls(self) -> int:
        return sum(self._calls.values())

    def model_stats(self, model_name: str) -> dict[str, Any]:
        """Get stats for a specific model."""
        latencies = self._latencies.get(model_name, [])
        return {
            "calls": self._calls.get(model_name, 0),
            "total_tokens": self._tokens.get(model_name, 0),
            "total_cost": round(self._costs.get(model_name, 0.0), 6),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "max_latency_ms": round(max(latencies), 1) if latencies else 0.0,
        }

    def summary(self) -> dict[str, Any]:
        """Get aggregate cost and latency summary."""
        per_model = {}
        for name in set(list(self._calls.keys()) + list(self._costs.keys())):
            per_model[name] = self.model_stats(name)

        return {
            "total_calls": self.total_calls,
            "total_cost": round(self.total_cost, 6),
            "total_tokens": sum(self._tokens.values()),
            "elapsed_seconds": round(time.time() - self._start_time, 1),
            "per_model": per_model,
        }

    def reset(self) -> None:
        self._costs.clear()
        self._calls.clear()
        self._latencies.clear()
        self._tokens.clear()
        self._start_time = time.time()


# ── AdaptiveRouter ─────────────────────────────────────────────────────────


class AdaptiveRouter:
    """Adaptive model router with capability, cost, and latency optimization.

    Extends the SmartRouter concept with:
      - ModelRegistry for declaring model capabilities and costs
      - CostTracker for tracking real usage
      - Adaptive selection: capability match → cost optimization → latency awareness
      - Fallback chains: try cheapest capable model, fall back on failure

    Usage:
        registry = ModelRegistry()
        registry.register("gpt-4o-mini", cost_per_1k=0.00015, ...)
        registry.register("gpt-4o", cost_per_1k=0.0025, ...)

        router = AdaptiveRouter(registry=registry)
        provider = await router.select("Hello")
        # Uses gpt-4o-mini

        provider = await router.select(
            "Write a complex algorithm",
            capabilities_needed={"reasoning"},
        )
        # Uses gpt-4o
    """

    def __init__(self, registry: ModelRegistry | None = None,
                 optimize_for: str = "cost",
                 cost_tracker: CostTracker | None = None):
        self._registry = registry or ModelRegistry()
        self._cost_tracker = cost_tracker or CostTracker()
        self._optimize_for = optimize_for  # "cost", "latency", "balanced"

    @property
    def registry(self) -> ModelRegistry:
        return self._registry

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost_tracker

    async def select(self, prompt: str,
                     capabilities_needed: set[str] | None = None,
                     max_cost: float | None = None) -> Any | None:
        """Select the best model for a given task.

        Args:
            prompt: The user prompt (used for complexity classification).
            capabilities_needed: Required capabilities (e.g., {"reasoning", "vision"}).
            max_cost: Max acceptable cost per 1K tokens.

        Returns:
            A configured LLM provider, or None if no model matches.
        """
        # Start with capability filter
        candidates = self._registry.all

        if capabilities_needed:
            for cap in capabilities_needed:
                candidates = [m for m in candidates if cap in m.capabilities]

        if max_cost is not None:
            candidates = [m for m in candidates if m.cost_per_1k <= max_cost]

        if not candidates:
            logger.warning(f"No model matches: caps={capabilities_needed}, max_cost={max_cost}")
            return None

        # Sort by optimization goal
        if self._optimize_for == "cost":
            candidates.sort(key=lambda m: m.cost_per_1k)
        elif self._optimize_for == "latency":
            candidates.sort(key=lambda m: m.latency_ms)
        else:  # balanced
            candidates.sort(key=lambda m: m.cost_per_1k * m.latency_ms)

        selected = candidates[0]
        logger.info(f"Adaptive route: {selected.name} "
                    f"(cost={selected.cost_per_1k}, latency={selected.latency_ms})")

        return self._create_provider(selected)

    def select_cheapest(self, capability: str | None = None) -> Any | None:
        """Get the cheapest model with the given capability."""
        info = self._registry.cheapest(capability)
        return self._create_provider(info) if info else None

    def select_most_capable(self) -> Any | None:
        """Get the most capable model."""
        info = self._registry.most_capable()
        return self._create_provider(info) if info else None

    async def fallback_chain(self, prompt: str,
                              capabilities_needed: set[str] | None = None
                              ) -> list[Any]:
        """Get a prioritized list of models as a fallback chain.

        The first model is the best match. If it fails, try the next, etc.

        Args:
            prompt: The user prompt.
            capabilities_needed: Required capabilities.

        Returns:
            Ordered list of LLM providers (best first).
        """
        candidates = self._registry.all

        if capabilities_needed:
            for cap in capabilities_needed:
                candidates = [m for m in candidates if cap in m.capabilities]

        if not candidates:
            candidates = self._registry.all

        candidates.sort(key=lambda m: m.cost_per_1k)
        return [self._create_provider(m) for m in candidates]

    def _create_provider(self, info: ModelInfo) -> Any | None:
        """Create an LLM provider from ModelInfo.

        Uses the appropriate provider class based on the provider field.
        """
        try:
            if info.provider == "openai":
                from chainforge.providers import OpenAIProvider
                return OpenAIProvider(model=info.name)
            elif info.provider == "anthropic":
                from chainforge.providers import AnthropicProvider
                return AnthropicProvider(model=info.name)
            elif info.provider == "google":
                from chainforge.providers import GoogleProvider
                return GoogleProvider(model=info.name)
            elif info.provider == "deepseek":
                from chainforge.providers import DeepSeekProvider
                return DeepSeekProvider(model=info.name)
            elif info.provider == "ollama":
                from chainforge.providers import OllamaProvider
                return OllamaProvider(model=info.name)
            else:
                from chainforge.providers import OpenAIProvider
                return OpenAIProvider(model=info.name)
        except Exception as e:
            logger.warning(f"Failed to create provider for {info.name}: {e}")
            return None

    def stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "registry_count": self._registry.count,
            "cost_tracker": self._cost_tracker.summary(),
            "optimize_for": self._optimize_for,
        }


__all__ = [
    "ModelRegistry",
    "ModelInfo",
    "CostTracker",
    "AdaptiveRouter",
]
