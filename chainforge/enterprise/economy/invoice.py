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
"""Invoice and revenue-report models for the Agent Economic Protocol."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class Invoice(BaseModel):
    """Bill for a buyer agent — summarizes what they owe."""

    agent_id: str = ""
    period: str = "all"
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_payable: float = 0.0
    generated_at: float = Field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        return self.model_dump()


class RevenueReport(BaseModel):
    """Revenue report for a seller agent — earned, settled, and outstanding."""

    agent_id: str = ""
    period: str = "all"
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_earned: float = 0.0
    total_settled: float = 0.0
    total_outstanding: float = 0.0
    generated_at: float = Field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        return self.model_dump()
