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
"""Agent runtime metrics collection for anomaly detection."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("enterprise.observe")


class MetricsCollector(BaseModel):
    """Collect agent runtime metrics for anomaly detection.

    Tracks: total_calls, failures, tools_called, tokens_used, cost, latency.
    All accessible via .stats property for feeding into AnomalyDetector.
    """

    total_calls: int = Field(default=0)
    failures: int = Field(default=0)
    total_tokens: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    latency_samples: list[float] = Field(default_factory=list)
    tools_seen: set[str] = Field(default_factory=set)
    timestamps: list[float] = Field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failures / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)

    @property
    def tokens_per_call(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_tokens / self.total_calls

    def record(
        self,
        success: bool,
        latency_ms: float,
        tokens: int,
        cost: float,
        tool_names: list[str],
    ) -> None:
        self.total_calls += 1
        self.total_tokens += tokens
        self.total_cost += cost
        self.latency_samples.append(latency_ms)
        if not success:
            self.failures += 1
        for t in tool_names:
            self.tools_seen.add(t)
        self.timestamps.append(time.time())
        # Cap samples at 1000 to bound memory
        if len(self.latency_samples) > 1000:
            self.latency_samples = self.latency_samples[-1000:]
        if len(self.timestamps) > 1000:
            self.timestamps = self.timestamps[-1000:]

    @property
    def stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "failure_rate": round(self.failure_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "tokens_per_call": round(self.tokens_per_call, 1),
            "total_cost": round(self.total_cost, 4),
            "tools_seen_count": len(self.tools_seen),
            "tools_seen": sorted(self.tools_seen),
        }
