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
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
import time
import uuid


class DLQItem(BaseModel):
    """An item in the Dead Letter Queue."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    job_id: str
    agent_id: str = ""
    step_index: int = 0
    failed_reason: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    enqueued_at: float = Field(default_factory=time.time)
    retry_count: int = 0


class DeadLetterQueue:
    """Stores failed jobs for manual inspection and retry."""

    def __init__(self, backend: str = "memory"):
        self._items: list[DLQItem] = []

    def enqueue(self, job_id: str, step_index: int = 0, reason: str = "",
                context: dict[str, Any] | None = None, agent_id: str = "") -> DLQItem:
        item = DLQItem(job_id=job_id, agent_id=agent_id, step_index=step_index,
                       failed_reason=reason, context=context or {})
        self._items.append(item)
        return item

    def list(self) -> list[DLQItem]:
        return list(self._items)

    def get(self, job_id: str) -> DLQItem | None:
        for i in self._items:
            if i.job_id == job_id:
                return i
        return None

    def retry(self, job_id: str) -> bool:
        item = self.get(job_id)
        if item:
            item.retry_count += 1
            self._items.remove(item)
            return True
        return False

    def discard(self, job_id: str) -> bool:
        item = self.get(job_id)
        if item:
            self._items.remove(item)
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._items)
