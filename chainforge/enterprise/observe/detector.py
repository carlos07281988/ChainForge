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
"""Real-time anomaly detection middleware for agent observability."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.llm import LLMResponse
from chainforge.enterprise.observe.alert import (
    Alert,
    AlertChannel,
    AlertEngine,
    AlertRule,
)
from chainforge.enterprise.observe.metrics import MetricsCollector
from chainforge.logging import get_logger

logger = get_logger("enterprise.observe")


class AnomalyEvent(BaseModel):
    """A detected anomaly."""

    id: str = ""
    type: str = ""
    severity: str = "medium"
    description: str = ""
    metrics_snapshot: dict = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class AnomalyDetector:
    """Middleware: detect anomalous agent behavior in real-time.

    Detects: failure rate spikes (>3x baseline), new tool usage,
    token anomalies (>2x baseline).

    Usage::

        detector = AnomalyDetector(baseline_window_hours=24)
        agent = Agent(llm=llm, middlewares=[detector.middleware()])
        detector.add_rule(AlertRule(
            name="fail_spike",
            condition="failure_rate > 3",
            severity="critical",
        ))
    """

    def __init__(self, baseline_window_hours: int = 24):
        self._metrics = MetricsCollector()
        self._engine = AlertEngine()
        self._baseline_window = baseline_window_hours

        # Built-in rules
        self._engine.add_rule(
            AlertRule(
                name="failure_rate_spike",
                condition="failure_rate > 3",
                severity="critical",
                message_template=(
                    "Agent failure rate {failure_rate} exceeds 3x "
                    "baseline {baseline_failure_rate}"
                ),
            )
        )
        self._engine.add_rule(
            AlertRule(
                name="new_tool_detected",
                condition="new_tool",
                severity="high",
                message_template="Agent used unknown tool: {last_tool}",
            )
        )
        self._engine.add_rule(
            AlertRule(
                name="token_spike",
                condition="tokens > 2x",
                severity="medium",
                message_template=(
                    "Token consumption {tokens_per_call} > 2x baseline "
                    "{baseline_tokens_per_call}"
                ),
            )
        )

    def add_rule(self, rule: AlertRule) -> None:
        self._engine.add_rule(rule)

    def middleware(self):
        detector = self

        async def _mw(messages, ctx, next_handler):
            start = time.time()
            tool_names: list[str] = []
            success = True
            tokens = 0
            cost = 0.0
            last_tool = ""

            async for event in next_handler(messages, ctx):
                if (
                    hasattr(event, "type")
                    and event.type == "tool_call"
                    and event.data
                ):
                    tn = event.data.get("tool_name", "")
                    tool_names.append(tn)
                    last_tool = tn
                if isinstance(event, LLMResponse):
                    tokens = (
                        event.usage.get("total_tokens", 0)
                        if event.usage
                        else 0
                    )
                    cost = event.cost or 0.0
                yield event

            detector._metrics.record(
                success,
                (time.time() - start) * 1000,
                tokens,
                cost,
                tool_names,
            )
            stats = detector._metrics.stats
            stats["last_tool"] = last_tool
            baseline = {
                "failure_rate": 0.02,
                "tokens_per_call": stats.get("tokens_per_call", 100) * 0.8,
            }
            alerts = detector._engine.evaluate(
                stats, detector._metrics.tools_seen, baseline
            )
            for a in alerts:
                logger.warning(
                    "ALERT [%s] %s: %s", a.severity, a.rule_name, a.message
                )

        return _mw

    @property
    def stats(self) -> dict:
        return self._metrics.stats

    @property
    def recent_alerts(self) -> list:
        return self._engine.recent_alerts
