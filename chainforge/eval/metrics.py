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
"""Metrics collection for agent evaluation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from chainforge.core.stream import EventType, StreamEvent


@dataclass
class CollectedMetrics:
    """Metrics collected from a single agent run."""
    response_time: float = 0.0
    tool_call_count: int = 0
    iterations: int = 0
    response_length: int = 0
    success: bool = True
    token_count: int = 0
    cost: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)
    raw_output: str = ""


class MetricsCollector:
    """Collects metrics by observing stream events from an agent run."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.metrics = CollectedMetrics()
        self._start_time: float | None = None
        self._text_parts: list[str] = []
        self._state_counts: dict[str, int] = {}

    async def collect(self, stream) -> CollectedMetrics:
        """Consume a stream and collect metrics."""
        self.reset()
        self._start_time = time.monotonic()
        async for event in stream:
            self._record_event(event)
        self.metrics.response_time = time.monotonic() - self._start_time
        self.metrics.raw_output = "".join(self._text_parts)
        self.metrics.response_length = len(self.metrics.raw_output)
        return self.metrics

    def _record_event(self, event: StreamEvent):
        ev = {"type": event.type.value, "content": event.content, "data": event.data}
        self.metrics.events.append(ev)

        if event.type == EventType.text and event.content:
            self._text_parts.append(event.content)

        if event.type == EventType.tool_call:
            self.metrics.tool_call_count += 1

        if event.type == EventType.error:
            self.metrics.success = False

        if event.type == EventType.state:
            state = event.data.get("state", "")
            self._state_counts[state] = self._state_counts.get(state, 0) + 1
            if "iteration" in event.data:
                self.metrics.iterations = max(self.metrics.iterations, event.data["iteration"] + 1)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "gpt-4o") -> float:
        """Estimate cost in USD based on token counts."""
        rates = {
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4": (30.00, 60.00),
            "claude-3-5-sonnet": (3.00, 15.00),
            "claude-3-haiku": (0.25, 1.25),
        }
        model_key = model.lower()
        if model_key in rates:
            input_rate, output_rate = rates[model_key]
        else:
            input_rate, output_rate = 1.00, 4.00
        return (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)


# Built-in metric definitions for reporting
BUILTIN_METRICS = {
    "response_time": {"label": "Response Time", "unit": "s", "higher_is_better": False},
    "tool_call_count": {"label": "Tool Calls", "unit": "calls", "higher_is_better": False},
    "iterations": {"label": "Iterations", "unit": "steps", "higher_is_better": False},
    "response_length": {"label": "Response Length", "unit": "chars", "higher_is_better": None},
    "success": {"label": "Success", "unit": "%", "higher_is_better": True},
    "token_count": {"label": "Token Usage", "unit": "tokens", "higher_is_better": False},
    "cost": {"label": "Estimated Cost", "unit": "USD", "higher_is_better": False},
}


def builtin_metrics() -> dict:
    """Return the built-in metric definitions."""
    return dict(BUILTIN_METRICS)
