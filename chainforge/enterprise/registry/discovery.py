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
"""Discovery query model for the CapabilityRegistry."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CapabilityQuery(BaseModel):
    """A discovery query for finding agents by capability."""

    capability: str | None = Field(
        default=None,
        description="Exact capability tag, e.g. 'postgresql:query'",
    )
    query: str | None = Field(
        default=None,
        description="Semantic search text for fuzzy matching",
    )
    min_availability: float = Field(default=0.0, ge=0.0, le=1.0)
    max_latency_ms: int | None = Field(default=None)
    max_cost: float | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)
