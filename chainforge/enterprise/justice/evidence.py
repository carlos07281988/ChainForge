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
"""Evidence primitives — immutable records of every step an agent took."""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """A single piece of evidence in the decision chain."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    step: int = 0
    event_type: str = ""  # user_input|llm_call|tool_call|tool_result|llm_response|final_output
    timestamp: float = Field(default_factory=time.time)
    content: str = ""
    model: str = ""  # which LLM model
    tool_name: str = ""
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: str = ""
    tokens_used: int = 0
    cost: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    """Complete evidence chain for a single agent run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str = ""
    created_at: float = Field(default_factory=time.time)
    items: list[EvidenceItem] = Field(default_factory=list)
    total_steps: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    duration_ms: float = 0.0
    agent_name: str = ""
    tools_available: list[str] = Field(default_factory=list)

    def to_json(self) -> dict:
        return self.model_dump()

    def timeline(self) -> str:
        """Human-readable timeline of the decision chain."""
        lines = [
            f"Decision Timeline: {self.run_id}",
            f"Agent: {self.agent_name}",
            f"Duration: {self.duration_ms:.0f}ms",
            "",
        ]
        for item in self.items:
            icon = {
                "user_input": "\U0001f4e5",
                "llm_call": "\U0001f9e0",
                "tool_call": "\U0001f527",
                "tool_result": "\U0001f4ca",
                "llm_response": "\U0001f4ac",
                "final_output": "✅",
            }.get(item.event_type, "❓")
            lines.append(f"  {icon} Step {item.step}: [{item.event_type}] {item.content[:120]}")
            if item.tool_name:
                lines.append(f"       Tool: {item.tool_name}({item.tool_args})")
        return "\n".join(lines)
