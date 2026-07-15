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
"""SmartRouter — classify task complexity and route to optimal model.

Reduces costs by routing simple tasks to cheap models (gpt-4o-mini)
and complex/reasoning tasks to capable models (gpt-4o, deepseek-reasoner).
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from chainforge.core.agent import Agent
from chainforge.core.llm import LLM, ProviderCapability
from chainforge.core.message import Message
from chainforge.core.stream import Stream
from chainforge.logging import get_logger

logger = get_logger("routing")

CLASSIFY_PROMPT = """Classify the following user request by complexity on a scale of 1-5.

1 = Very simple (greeting, yes/no, trivial fact)
2 = Simple (basic Q&A, straightforward lookup)
3 = Moderate (multi-step reasoning, comparison, analysis)
4 = Complex (deep reasoning, code generation, math)
5 = Very complex (research, planning, novel solutions)

Respond with ONLY a number 1-5."""


class RoutingStrategy(str, Enum):
    """Available routing strategies."""
    COST_OPTIMIZED = "cost_optimized"       # Cheap model for simple, expensive for complex
    FALLBACK = "fallback"                   # Start cheap, upgrade on failure
    CAPABILITY = "capability"               # Match task to model capabilities


class RouteConfig:
    """Configuration for a single route."""
    def __init__(self, name: str, llm: LLM, max_complexity: int = 5, capabilities: set[str] | None = None):
        self.name = name
        self.llm = llm
        self.max_complexity = max_complexity
        self.capabilities = capabilities or set()

    def can_handle(self, complexity: int, needed_capabilities: set[str] | None = None) -> bool:
        if complexity > self.max_complexity:
            return False
        if needed_capabilities:
            llm_caps = getattr(self.llm, "capabilities", set())
            if not needed_capabilities.issubset(llm_caps):
                return False
        return True


class SmartRouter:
    """Route tasks to the optimal LLM based on task complexity and capabilities.

    Usage:
        router = SmartRouter(strategy=RoutingStrategy.COST_OPTIMIZED)
        router.register("fast", gpt4o_mini, max_complexity=2)
        router.register("reasoning", deepseek_r1, max_complexity=5)
        router.register("default", gpt4o, max_complexity=5)

        agent = router.create_cost_optimized_agent(tools=[...])
        result = await router.run(agent, "What is 2+2?")
        # Uses gpt-4o-mini (fast, cheap)
        result = await router.run(agent, "Solve this complex math problem")
        # Uses gpt-4o or deepseek-reasoner
    """

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.COST_OPTIMIZED):
        self.strategy = strategy
        self._routes: dict[str, RouteConfig] = {}

    def register(
        self,
        name: str,
        llm: LLM,
        max_complexity: int = 5,
        capabilities: set[str] | None = None,
    ) -> "SmartRouter":
        """Register a model route.

        Args:
            name: Route identifier.
            llm: LLM provider instance.
            max_complexity: Max task complexity this model handles (1-5).
            capabilities: Required capabilities (e.g., {ProviderCapability.REASONING}).
        """
        self._routes[name] = RouteConfig(
            name=name,
            llm=llm,
            max_complexity=max_complexity,
            capabilities=capabilities or set(),
        )
        logger.info(f"Route '{name}': {llm.model} (max_complexity={max_complexity})")
        return self

    async def classify(self, prompt: str) -> int:
        """Classify task complexity (1-5) using a cheap classification model."""
        # Use first registered route's LLM or a default classifier
        classifier_llm = None
        for route in self._routes.values():
            if "mini" in str(route.llm.model).lower() or "flash" in str(route.llm.model).lower():
                classifier_llm = route.llm
                break
        if classifier_llm is None and self._routes:
            # Pick the first route with max_complexity >= 3
            for route in self._routes.values():
                if route.max_complexity >= 3:
                    classifier_llm = route.llm
                    break
            if classifier_llm is None:
                classifier_llm = next(iter(self._routes.values())).llm

        try:
            resp = await classifier_llm.generate([Message.user(CLASSIFY_PROMPT + f"\n\n{prompt}")])
            text = (resp.content or "").strip()
            complexity = int(text[0]) if text and text[0].isdigit() else 3
            return max(1, min(5, complexity))
        except Exception:
            return 3

    def select_route(self, complexity: int, needed_capabilities: set[str] | None = None) -> tuple[str, LLM] | None:
        """Select the best route for the given complexity and capabilities."""
        if self.strategy == RoutingStrategy.COST_OPTIMIZED:
            return self._select_cost_optimized(complexity, needed_capabilities)
        elif self.strategy == RoutingStrategy.FALLBACK:
            return self._select_fallback(complexity, needed_capabilities)
        elif self.strategy == RoutingStrategy.CAPABILITY:
            return self._select_capability(complexity, needed_capabilities)
        return None

    def _select_cost_optimized(self, complexity: int, needed: set[str] | None) -> tuple[str, LLM] | None:
        """Select the cheapest model that can handle the task."""
        candidates = []
        for name, route in self._routes.items():
            if route.can_handle(complexity, needed):
                candidates.append((route.max_complexity, name, route))
        if not candidates:
            return None
        # Prefer the one with LOWEST max_complexity that still covers our needs
        candidates.sort(key=lambda x: (x[0] if x[0] >= complexity else 99, x[0]))
        best = candidates[0]
        return best[1], best[2].llm

    def _select_fallback(self, complexity: int, needed: set[str] | None) -> tuple[str, LLM] | None:
        """Select the model and allow fallback chain."""
        best = None
        best_complexity = -1
        for name, route in self._routes.items():
            if route.can_handle(complexity, needed) and route.max_complexity > best_complexity:
                best = (name, route.llm)
                best_complexity = route.max_complexity
        return best

    def _select_capability(self, complexity: int, needed: set[str] | None) -> tuple[str, LLM] | None:
        """Select based on capability match."""
        if not needed:
            return self._select_cost_optimized(complexity, None)
        for name, route in sorted(self._routes.items(), key=lambda x: x[1].max_complexity):
            if route.can_handle(complexity, needed):
                return name, route.llm
        return self._select_cost_optimized(complexity, None)

    def get_llm(self, prompt: str, needed_capabilities: set[str] | None = None) -> tuple[str, LLM]:
        """Classify and select the best LLM for a prompt.

        Returns:
            (route_name, llm_provider) tuple.
        """
        complexity = asyncio_run(self.classify(prompt))
        result = self.select_route(complexity, needed_capabilities)
        if result is None:
            raise ValueError(f"No route can handle complexity {complexity}")
        logger.info(f"Routed (complexity={complexity}): {result[0]}")
        return result

    def create_cost_optimized_agent(
        self,
        tools: list | None = None,
        system_prompt: str | None = None,
    ) -> Agent:
        """Create an Agent that automatically uses the best model for each task.

        The agent wraps the SmartRouter's classification logic.
        """
        return SmartRoutingAgent(self, tools=tools, system_prompt=system_prompt)


class SmartRoutingAgent:
    """An Agent wrapper that routes each invocation to the optimal LLM.

    Usage:
        router = SmartRouter()
        router.register("fast", OpenAIProvider(model="gpt-4o-mini"), max_complexity=2)
        router.register("default", OpenAIProvider(model="gpt-4o"), max_complexity=5)

        agent = router.create_cost_optimized_agent(tools=[get_weather])
        async for event in await agent.run("Weather in Beijing?"):
            # Routes to gpt-4o-mini for simple weather lookups
            ...
    """

    def __init__(self, router: SmartRouter, tools=None, system_prompt=None):
        self._router = router
        self.tools = tools or []
        self.system_prompt = system_prompt

    async def run(self, prompt: str | list[Message], *, context=None) -> Stream:
        """Run with automatic model routing."""
        prompt_str = prompt if isinstance(prompt, str) else (prompt[-1].content if prompt[-1].content else "")

        # Classify and select model
        complexity = await self._router.classify(prompt_str)
        route_name, llm = self._router.select_route(complexity) or (None, None)
        if llm is None:
            raise ValueError("No route available")

        logger.info(f"SmartAgent: complexity={complexity}, route={route_name}, model={llm.model}")

        # Create a temporary agent with the selected LLM
        agent = Agent(
            llm=llm,
            tools=list(self.tools),
            system_prompt=self.system_prompt,
        )
        return await agent.run(prompt, context=context)

    @property
    def llm(self):
        """Return the default LLM (used by Agent introspection)."""
        _, llm = self._router.select_route(3) or (None, None)
        return llm or LLM()


try:
    from chainforge.core.utils import run_sync
    asyncio_run = run_sync
except ImportError:
    import asyncio
    def asyncio_run(coro):
        return asyncio.get_event_loop().run_until_complete(coro)
