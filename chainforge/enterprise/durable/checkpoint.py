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
from pydantic import BaseModel, ConfigDict, Field
import json
import time
import uuid


class Checkpoint(BaseModel):
    """A single execution checkpoint that enables crash recovery."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    job_id: str = ""
    step_index: int = 0
    total_steps: int = 0
    messages_json: str = "[]"             # Serialized list of Message dicts
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    cost_accumulated: float = 0.0
    tool_results_cached: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    @classmethod
    def from_messages(cls, job_id: str, step_index: int, total_steps: int,
                      messages: list[Any], state: dict, tokens: int, cost: float,
                      tool_results: dict) -> Checkpoint:
        try:
            msgs_json = json.dumps([m.model_dump() if hasattr(m, 'model_dump') else str(m) for m in messages])
        except Exception:
            msgs_json = json.dumps([str(m) for m in messages])
        return cls(job_id=job_id, step_index=step_index, total_steps=total_steps,
                   messages_json=msgs_json, state_snapshot=state, tokens_used=tokens,
                   cost_accumulated=cost, tool_results_cached=tool_results)

    def to_json(self) -> dict:
        return self.model_dump()
