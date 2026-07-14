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
