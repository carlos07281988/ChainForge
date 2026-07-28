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
"""CostReport + CostOptimization -- queryable billing data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CostReport(BaseModel):
    """Aggregated cost report.

    Attributes:
        total: Total cost in USD.
        rows: Aggregated rows with dimension, calls, tokens, cost.
        group_by: Which dimension was used for grouping.
        period: Time period string.
    """

    total: float = Field(default=0.0)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    group_by: str = Field(default="model")
    period: str = Field(default="all")

    def to_json(self) -> list[dict[str, Any]]:
        """Export rows as a JSON-serializable list.

        Suitable for feeding into Grafana, DataDog, Prometheus, or
        any observability dashboard via custom exporter.
        """
        return self.rows


class CostOptimization(BaseModel):
    """Cost optimization suggestions from historical analysis.

    Attributes:
        potential_savings: Estimated annual savings in USD.
        items: Human-readable suggestion strings.
    """

    potential_savings: float = Field(default=0.0)
    items: list[str] = Field(default_factory=list)
