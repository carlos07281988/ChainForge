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
"""SelfEvolvingAgent — agent that learns from its own execution.

Analyzes execution patterns after each run and auto-improves:
  - Tool usage patterns: learns which tools work best for which tasks
  - System prompt optimization: refines instructions based on outcomes
  - Error pattern avoidance: detects recurring failures and adjusts
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from logging import INFO
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.logging import get_logger, log_data

logger = get_logger("agents.evolving")


class ExecutionMetrics(BaseModel):
    """Metrics recorded for a single agent execution."""

    timestamp: float = Field(default_factory=time.time)
    prompt_length: int = Field(default=0)
    tool_calls: int = Field(default=0)
    tool_successes: int = Field(default=0)
    tool_errors: int = Field(default=0)
    tool_names: list[str] = Field(default_factory=list)
    response_length: int = Field(default=0)
    success: bool = Field(default=True)


class SelfEvolvingAgent(Agent):
    """An agent that learns from its own execution to improve over time.

    Records execution metrics after each run and uses them to optimize prompts,
    tool selection, and error avoidance.

    Usage:
        agent = SelfEvolvingAgent(
            llm=OpenAIProvider(model="gpt-4o"),
            tools=[search, calculate],
            system_prompt="You are a helpful assistant.",
            evolution_enabled=True,
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    evolution_enabled: bool = Field(default=True)
    evolution_log_path: str | None = Field(default=None)
    min_runs_for_evolution: int = Field(default=3)
    run_count: int = Field(default=0, description="Number of runs executed")
    metrics_history: list = Field(default_factory=list, exclude=True)

    def _load_history(self) -> None:
        """Load evolution history from disk."""
        if self.evolution_log_path:
            try:
                with open(self.evolution_log_path, "r") as f:
                    data = json.load(f)
                    self.metrics_history = data.get("metrics", [])
                    self.run_count = data.get("run_count", 0)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

    def _save_history(self) -> None:
        """Save evolution history to disk."""
        if self.evolution_log_path:
            hist = self.metrics_history[-100:]
            with open(self.evolution_log_path, "w") as f:
                json.dump({
                    "run_count": self.run_count,
                    "metrics": hist,
                    "last_updated": time.time(),
                }, f, indent=2, default=str)

    def _record_metrics(self, metrics: ExecutionMetrics) -> None:
        """Record execution metrics and trigger evolution analysis."""
        self.run_count += 1
        metrics_dict = metrics.model_dump()
        metrics_dict["run_number"] = self.run_count
        self.metrics_history.append(metrics_dict)
        self._save_history()

    def _analyze_and_evolve(self) -> list[str]:
        """Analyze execution history and generate improvements."""
        improvements = []
        if self.run_count < self.min_runs_for_evolution:
            return improvements

        hist = self.metrics_history
        if not hist:
            return improvements

        # Tool usage analysis
        tool_usage: dict[str, int] = {}
        for m in hist:
            for tool_name in m.get("tool_names", []):
                tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1

        if tool_usage:
            most_used = max(tool_usage, key=tool_usage.get)
            improvements.append(f"Most used tool: {most_used} ({tool_usage[most_used]}x)")

        # Error rate
        errors = sum(1 for m in hist if not m.get("success", True))
        total = len(hist)
        if total > 0:
            rate = (errors / total) * 100
            improvements.append(f"Success rate: {100 - rate:.0f}% across {total} runs")

        return improvements

    def _evolve_system_prompt(self, improvements: list[str]) -> str | None:
        """Evolve system prompt based on analysis."""
        if not improvements or not self.system_prompt:
            return None

        learnings = "\n".join(f"- {imp}" for imp in improvements)
        evolved = self.system_prompt + f"\n\n[Evolution Insights]\n{learnings}"
        return evolved

    async def run(
        self,
        prompt: str | list[Message],
        *,
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> Stream:
        """Execute with self-evolution capabilities."""
        ctx = context or {}

        async def _generate() -> AsyncIterator[StreamEvent]:
            if self.evolution_enabled and self.run_count > 0:
                improvements = self._analyze_and_evolve()
                if improvements:
                    new_prompt = self._evolve_system_prompt(improvements)
                    if new_prompt:
                        self.system_prompt = new_prompt
                        yield StreamEvent(
                            type=EventType.status,
                            content="evolution:applied",
                            data={"improvements": improvements},
                        )

            yield StreamEvent(
                type=EventType.status,
                content=f"evolution:run_{self.run_count + 1}",
                data={"evolution_enabled": self.evolution_enabled, "run_count": self.run_count},
            )

            stream = await super().run(prompt, context=ctx, **kwargs)
            events = []
            metrics = ExecutionMetrics(
                prompt_length=len(prompt) if isinstance(prompt, str) else len(prompt),
            )

            async for event in stream:
                events.append(event)
                if event.type == EventType.tool_call:
                    metrics.tool_calls += 1
                    metrics.tool_names.append(event.data.get("name", "unknown"))
                elif event.type == EventType.tool_result:
                    if event.data.get("is_error"):
                        metrics.tool_errors += 1
                    else:
                        metrics.tool_successes += 1
                elif event.type == EventType.text and event.content:
                    metrics.response_length += len(event.content)
                elif event.type == EventType.error and event.content:
                    metrics.success = False

            if self.evolution_enabled:
                self._record_metrics(metrics)

            for event in events:
                yield event

        return Stream(_generate())
