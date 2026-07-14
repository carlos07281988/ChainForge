# Copyright 2024 ChainForge Contributors
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
"""Task queue with priority scheduling for the fleet worker pool."""

from __future__ import annotations

import asyncio
import enum
import heapq
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from chainforge.logging import get_logger

logger = get_logger("fleet.queue")


class TaskPriority(int, enum.Enum):
    """Priority levels for tasks."""
    critical = 0
    high = 1
    normal = 2
    low = 3


@dataclass(order=True)
class Task:
    """A unit of work for the agent fleet."""

    priority: TaskPriority = TaskPriority.normal
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = field(default="", compare=False)
    prompt: str = field(default="", compare=False)
    context: dict[str, Any] | None = field(default=None, compare=False)
    result: str | None = field(default=None, compare=False)
    error: str | None = field(default=None, compare=False)
    completed_at: float | None = field(default=None, compare=False)

    @property
    def duration_s(self) -> float:
        if self.completed_at:
            return round(self.completed_at - self.created_at, 3)
        return 0.0

    @property
    def wait_s(self) -> float:
        return round(time.time() - self.created_at, 1)


class TaskQueue:
    """Priority-based async task queue for agent execution.

    Usage:
        queue = TaskQueue()

        # Add tasks
        queue.put("agent-1", "Hello!", priority=TaskPriority.high)
        queue.put("agent-1", "Background task", priority=TaskPriority.low)

        # Consume tasks
        task = await queue.get()
        result = await pool.run(task.agent_id, task.prompt)
        queue.complete(task, result=result)
    """

    def __init__(self):
        self._heap: list[Task] = []
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()
        self._completed: list[Task] = []
        self._total_added = 0
        self._total_completed = 0

    def put(
        self,
        agent_id: str,
        prompt: str,
        *,
        priority: TaskPriority = TaskPriority.normal,
        context: dict[str, Any] | None = None,
    ) -> Task:
        """Add a task to the queue.

        Args:
            agent_id: Target agent identifier.
            prompt: Input prompt.
            priority: Task priority.
            context: Optional context.

        Returns:
            The created Task.
        """
        task = Task(
            priority=priority,
            agent_id=agent_id,
            prompt=prompt,
            context=context,
        )
        heapq.heappush(self._heap, task)
        self._total_added += 1
        self._event.set()
        return task

    async def get(self) -> Task:
        """Get the highest-priority task from the queue.

        Blocks until a task is available.
        """
        while True:
            async with self._lock:
                if self._heap:
                    task = heapq.heappop(self._heap)
                    return task
            self._event.clear()
            await self._event.wait()

    def complete(self, task: Task, result: str | None = None, error: str | None = None) -> None:
        """Mark a task as completed.

        Args:
            task: The task to complete.
            result: Task output text.
            error: Error message if failed.
        """
        task.result = result
        task.error = error
        task.completed_at = time.time()
        self._completed.append(task)
        self._total_completed += 1

    def peek(self) -> Task | None:
        """View the highest-priority task without removing it."""
        return self._heap[0] if self._heap else None

    @property
    def pending_count(self) -> int:
        return len(self._heap)

    @property
    def completed_count(self) -> int:
        return self._total_completed

    def stats(self) -> dict[str, Any]:
        return {
            "pending": self.pending_count,
            "completed": self.completed_count,
            "total_added": self._total_added,
        }
