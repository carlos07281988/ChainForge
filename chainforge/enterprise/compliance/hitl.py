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
"""HITLPolicy — human-in-the-loop enforcement for high-risk agent actions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.compliance.classifier import RiskTier


class ApprovalRequest(BaseModel):
    """An approval request sent to a human reviewer."""

    request_id: str = Field(description="Unique request identifier")
    agent_name: str = Field(default="unknown")
    action: str = Field(default="", description="What the agent wants to do")
    risk_tier: RiskTier = Field(default=RiskTier.MINIMAL)
    reason: str = Field(default="")
    context: dict[str, Any] = Field(default_factory=dict)


ApprovalHandler = Callable[[ApprovalRequest], Awaitable[bool]]
"""An async function that receives an ApprovalRequest and returns True to approve."""


class HITLPolicy(BaseModel):
    """Policy for when human approval is required.

    Usage:
        async def my_handler(req: ApprovalRequest) -> bool:
            # Send to Slack, PagerDuty, email, etc.
            return True

        policy = HITLPolicy(
            require_approval_on=[RiskTier.HIGH],
            approval_handler=my_handler,
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    require_approval_on: list[RiskTier] = Field(
        default_factory=lambda: [RiskTier.HIGH],
        description="Risk tiers that require human approval",
    )
    approval_handler: ApprovalHandler | None = Field(
        default=None,
        description="Custom approval handler (async function)",
    )

    def needs_approval(self, tier: RiskTier) -> bool:
        """Check if the given risk tier requires human approval."""
        return tier in self.require_approval_on
