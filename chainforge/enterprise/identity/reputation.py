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
"""ReputationEngine — event-based reputation scoring for agent identities."""

from __future__ import annotations

import time
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class ReputationScore(BaseModel):
    """A multi-dimensional reputation score for one agent.

    All dimension scores are in the range [0, 100]; *overall* is a
    weighted average of the four dimensions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_id: str
    overall: float = 0.0
    reliability: float = 0.0
    latency: float = 100.0
    safety: float = 100.0
    accuracy: float = 100.0
    total_calls: int = 0
    incident_count: int = 0

    computed_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Event-tracking data structures
# ---------------------------------------------------------------------------

class _AgentEvents:
    """Per-agent event counters (internal)."""

    __slots__ = (
        "successful_call",
        "failure",
        "prompt_injection_attempt",
        "data_exfiltration",
        "accurate_tool_choice",
        "wrong_tool_choice",
        "latency_values",
    )

    def __init__(self) -> None:
        self.successful_call: int = 0
        self.failure: int = 0
        self.prompt_injection_attempt: int = 0
        self.data_exfiltration: int = 0
        self.accurate_tool_choice: int = 0
        self.wrong_tool_choice: int = 0
        self.latency_values: list[float] = []


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ReputationEngine:
    """Collects events and produces ``ReputationScore`` instances.

    Typical usage::

        engine = ReputationEngine()
        engine.record_event("agent-1", "successful_call", latency_ms=120)
        score = engine.score("agent-1")
    """

    def __init__(self) -> None:
        self._events: dict[str, _AgentEvents] = defaultdict(_AgentEvents)

    # ------------------------------------------------------------------
    # Event recording
    # ------------------------------------------------------------------

    def record_event(
        self, agent_id: str, event_type: str, **data: object
    ) -> None:
        """Register an event for *agent_id*.

        Supported *event_type* values and their optional *data* kwargs
        --------------------------------------------------------------
        ``successful_call``       *latency_ms* (float/int)
        ``failure``               --
        ``prompt_injection_attempt`` --
        ``data_exfiltration``     --
        ``accurate_tool_choice``   --
        ``wrong_tool_choice``     --
        """
        ev = self._events[agent_id]

        if event_type == "successful_call":
            ev.successful_call += 1
            latency = float(data.get("latency_ms", 0))
            ev.latency_values.append(latency)
        elif event_type == "failure":
            ev.failure += 1
        elif event_type == "prompt_injection_attempt":
            ev.prompt_injection_attempt += 1
        elif event_type == "data_exfiltration":
            ev.data_exfiltration += 1
        elif event_type == "accurate_tool_choice":
            ev.accurate_tool_choice += 1
        elif event_type == "wrong_tool_choice":
            ev.wrong_tool_choice += 1

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score(self, agent_id: str) -> ReputationScore:
        """Compute the current reputation score for *agent_id*."""
        ev = self._events[agent_id]

        total = ev.successful_call + ev.failure
        reliability = (ev.successful_call / total * 100) if total > 0 else 100.0

        # Latency: baseline 2 000 ms. 0 ms → 100, >= 2 000 ms → 0.
        if ev.latency_values:
            avg = sum(ev.latency_values) / len(ev.latency_values)
            latency = max(0.0, min(100.0, 100.0 * (1.0 - avg / 2000.0)))
        else:
            latency = 100.0

        # Safety starts perfect and is penalized per incident.
        safety = max(
            0.0,
            100.0
            - ev.prompt_injection_attempt * 30.0
            - ev.data_exfiltration * 30.0,
        )

        # Accuracy: correct vs wrong tool choices.
        tool_total = ev.accurate_tool_choice + ev.wrong_tool_choice
        accuracy = (
            (ev.accurate_tool_choice / tool_total * 100)
            if tool_total > 0
            else 100.0
        )

        incidents = (
            ev.prompt_injection_attempt
            + ev.data_exfiltration
            + ev.failure
        )

        # Weighted overall: reliability 35%, latency 15%, safety 35%, accuracy 15%
        overall = round(
            reliability * 0.35
            + latency * 0.15
            + safety * 0.35
            + accuracy * 0.15,
            2,
        )

        return ReputationScore(
            agent_id=agent_id,
            overall=overall,
            reliability=round(reliability, 2),
            latency=round(latency, 2),
            safety=round(safety, 2),
            accuracy=round(accuracy, 2),
            total_calls=total,
            incident_count=incidents,
        )

    def all_scores(self) -> list[ReputationScore]:
        """Return reputation scores for every tracked agent."""
        return [self.score(aid) for aid in self._events]
