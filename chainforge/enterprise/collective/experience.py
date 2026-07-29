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
"""Experience — data model for shared agent experiences."""
from __future__ import annotations
from pydantic import BaseModel, Field

class Experience(BaseModel):
    """A single shared experience from an agent execution."""
    id: str = Field(description="Unique experience identifier")
    task: str = Field(default="", description="Summary of the user request")
    task_type: str = Field(default="general", description="refund_request, qa, code_gen, etc.")
    tools_used: list[str] = Field(default_factory=list)
    model_used: str = Field(default="unknown")
    outcome: str = Field(default="unknown", description="success | failure | partial")
    feedback: str | None = Field(default=None, description="Optional human feedback")
    cost: float = Field(default=0.0)
    tokens: int = Field(default=0)
    duration_ms: float = Field(default=0.0)
    timestamp: float = Field(default=0.0)
    decay_factor: float = Field(default=1.0, description="Current decay multiplier (1.0 = fresh)")
