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
"""Agent profiles and SLA definitions for the CapabilityRegistry."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ServiceLevelAgreement(BaseModel):
    """SLA constraints for an agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_latency_ms: int = Field(default=500)
    availability: float = Field(default=0.99, ge=0.0, le=1.0)


class AgentProfile(BaseModel):
    """Description of an agent registered in the CapabilityRegistry."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_id: str = Field(description="Unique agent identifier")
    name: str = Field(description="Human-readable name")
    version: str = Field(default="1.0.0")
    capabilities: list[str] = Field(
        default_factory=list,
        description="e.g. ['postgresql:query', 'sql:generate']",
    )
    tools_exposed: list[str] = Field(
        default_factory=list,
        description="Tool names available to callers",
    )
    endpoints: dict[str, str] = Field(
        default_factory=dict,
        description="{'a2a': '...', 'http': '...'}",
    )
    health_check_url: str = Field(default="")
    pricing: dict[str, float] = Field(
        default_factory=dict,
        description="{'per_query': 0.001}",
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="{'max_concurrent': 10}",
    )
    sla: ServiceLevelAgreement = Field(default_factory=ServiceLevelAgreement)
    supersedes: list[str] = Field(
        default_factory=list,
        description="Versions this profile replaces",
    )
    registered_at: float = Field(
        default_factory=lambda: __import__("time").time(),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
