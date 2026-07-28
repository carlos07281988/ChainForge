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
"""GDPR erasure models — ErasureItem, ErasureRequest, ErasureReport."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErasureItem(BaseModel):
    """Result of erasing a single data location."""

    location: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending|erased|failed|skipped
    detail: str = ""


class ErasureRequest(BaseModel):
    """A GDPR Article 17 Right-to-Erasure request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    data_subjects: list[dict] = Field(default_factory=list)  # serialized DataSubject dicts
    reason: str = "GDPR Article 17 — Right to Erasure"
    requested_by: str = ""
    deadline_hours: int = 72
    created_at: float = Field(default_factory=time.time)


class ErasureReport(BaseModel):
    """Report after executing an erasure request."""

    request_id: str = ""
    status: str = "pending"  # complete|partial|failed
    items: list[ErasureItem] = Field(default_factory=list)
    completed_items: int = 0
    pending_items: int = 0
    total_items: int = 0
    generated_at: float = Field(default_factory=time.time)

    @property
    def completion_rate(self) -> float:
        if self.total_items == 0:
            return 1.0
        return self.completed_items / self.total_items

    def to_json(self) -> dict:
        return self.model_dump()

    def summary(self) -> str:
        lines = [
            f"Erasure Report: {self.request_id}",
            f"Status: {self.status}",
            f"Completed: {self.completed_items}/{self.total_items}",
            f"Pending: {self.pending_items}",
        ]
        for item in self.items:
            icon = "✅" if item.status == "erased" else ("⚠️" if item.status == "pending" else "❌")
            lines.append(
                f"  {icon} {item.location.get('type', '?')} @ {item.location.get('provider', '?')}: {item.detail}"
            )
        return "\n".join(lines)
