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
"""Auto-negotiation with the CapabilityRegistry for the best matching agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NegotiationResult(BaseModel):
    """Result of auto-negotiation between requester and providers."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    accepted: bool = False
    provider: Any = None  # AgentProfile or None
    contract: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[Any] = Field(default_factory=list)
    reason: str = ""


class AutoNegotiation:
    """Auto-negotiate with the CapabilityRegistry for the best matching agent.

    Usage::

        negotiation = AutoNegotiation(
            requester_id="agent-a",
            capability_needed="postgresql:query",
            constraints={"max_cost_per_call": 0.01, "max_latency_ms": 500},
            registry=my_registry,
        )
        result = await negotiation.start()
        if result.accepted:
            provider = result.provider  # AgentProfile
    """

    def __init__(
        self,
        requester_id: str,
        capability_needed: str,
        constraints: dict[str, Any] | None = None,
        registry: Any = None,
    ) -> None:
        self._requester = requester_id
        self._capability = capability_needed
        self._constraints = constraints or {}
        self._registry = registry

    async def start(self) -> NegotiationResult:
        """Execute the negotiation against the configured registry."""
        if not self._registry:
            return NegotiationResult(reason="No registry configured")

        matches = await self._registry.discover(
            capability=self._capability,
            max_latency_ms=self._constraints.get("max_latency_ms"),
            max_cost=self._constraints.get("max_cost_per_call"),
            limit=3,
        )

        if not matches:
            return NegotiationResult(
                reason=f"No agents found for '{self._capability}'",
            )

        best_profile, score = matches[0]
        alternatives = [p for p, _ in matches[1:]]
        contract: dict[str, Any] = {
            "agent_id": best_profile.agent_id,
            "pricing": best_profile.pricing,
            "sla": best_profile.sla.model_dump(),
            "match_score": score,
        }

        return NegotiationResult(
            accepted=True,
            provider=best_profile,
            contract=contract,
            alternatives=alternatives,
            reason="Best match selected",
        )
