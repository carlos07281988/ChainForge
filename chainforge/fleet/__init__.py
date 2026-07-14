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
"""Fleet Management — worker pool and task queue for agent execution.

Provides:
  - Worker: wraps an agent instance for concurrent execution
  - WorkerPool: manages multiple workers with task distribution
  - TaskQueue: priority-based task scheduling

Usage:
    from chainforge.fleet import WorkerPool

    pool = WorkerPool(workers=4)
    pool.register("agent-1", my_agent)

    result = await pool.run("agent-1", "What is the weather?")
    print(result)
"""

from chainforge.fleet.worker import Worker, WorkerPool
from chainforge.fleet.queue import Task, TaskQueue, TaskPriority

__all__ = [
    "Worker",
    "WorkerPool",
    "Task",
    "TaskQueue",
    "TaskPriority",
]
