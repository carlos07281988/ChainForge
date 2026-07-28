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
"""Pricing contract and transaction models for the Agent Economic Protocol."""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, ConfigDict, Field


class BillingContract(BaseModel):
    """Pricing contract for a seller agent.

    Defines the pricing model, free quota, and approval thresholds
    that govern cross-agent tool-call billing.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pricing: dict[str, float] = Field(
        default_factory=lambda: {"per_tool_call": 0.001},
        description="Pricing model name -> unit price map (e.g. {'per_tool_call': 0.05}).",
    )
    free_quota: int = Field(
        default=0,
        description="Free calls per day before billing kicks in.",
    )
    require_approval_above: float | None = Field(
        default=None,
        description="Require approval for any single transaction exceeding this amount.",
    )


class Transaction(BaseModel):
    """A single cross-agent billing record.

    Captured every time one agent invokes a tool exposed by another agent.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    from_agent_id: str = ""
    to_agent_id: str = ""
    tool_name: str = ""
    pricing_model: str = "per_tool_call"
    unit_price: float = 0.0
    quantity: int = 1
    total_amount: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    settled: bool = False
