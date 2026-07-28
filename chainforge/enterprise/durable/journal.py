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
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
import time


class JournalStep(BaseModel):
    """A single step in the execution journal."""
    job_id: str
    step_index: int = 0
    event_type: str = ""  # started | checkpoint | tool_call | llm_call | completed | failed
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    cost_snapshot: float = 0.0
    tokens_snapshot: int = 0


class ExecutionJournal:
    """Records step-by-step execution history for audit and debugging."""

    def __init__(self, backend: str = "memory"):
        self._steps: list[JournalStep] = []

    def record(self, job_id: str, step_index: int, event_type: str,
               detail: str = "", data: dict[str, Any] | None = None,
               cost: float = 0.0, tokens: int = 0) -> JournalStep:
        step = JournalStep(job_id=job_id, step_index=step_index, event_type=event_type,
                           detail=detail, data=data or {}, cost_snapshot=cost, tokens_snapshot=tokens)
        self._steps.append(step)
        return step

    def trace(self, job_id: str) -> list[JournalStep]:
        return [s for s in self._steps if s.job_id == job_id]

    def all_traces(self) -> list[JournalStep]:
        return list(self._steps)

    def cost_at_checkpoint(self, step_index: int) -> float:
        total = 0.0
        for s in self._steps:
            if s.step_index <= step_index:
                total = s.cost_snapshot
        return total

    def summary(self, job_id: str) -> dict:
        steps = self.trace(job_id)
        if not steps:
            return {"job_id": job_id, "total_steps": 0, "events": [],
                    "total_cost": 0.0, "total_tokens": 0, "duration_seconds": 0.0}
        return {"job_id": job_id, "total_steps": len(steps),
                "events": [s.event_type for s in steps],
                "total_cost": sum(s.cost_snapshot for s in steps),
                "total_tokens": sum(s.tokens_snapshot for s in steps),
                "duration_seconds": max(s.timestamp for s in steps) - min(s.timestamp for s in steps)}
