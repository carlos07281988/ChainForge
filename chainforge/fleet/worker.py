"""Worker and WorkerPool — manage agent execution across concurrent workers."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger, log_data

logger = get_logger("fleet.worker")

import logging


class WorkerState(str):
    idle = "idle"
    busy = "busy"
    error = "error"
    stopped = "stopped"


@dataclass
class Worker:
    """A worker that wraps an agent for concurrent execution.

    Args:
        agent_id: Agent identifier.
        agent: The ChainForge Agent instance.
        max_concurrent: Max concurrent tasks (default 1).
    """

    agent_id: str
    agent: Any
    max_concurrent: int = 1
    state: str = "idle"
    current_task: str | None = None
    tasks_completed: int = 0
    total_duration_s: float = 0.0
    _semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(1))

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    async def run(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Execute the agent with the given prompt.

        Args:
            prompt: Input prompt.
            context: Optional context data.

        Returns:
            Agent's text output.
        """
        task_id = str(uuid.uuid4())
        self.state = "busy"
        self.current_task = task_id
        start = time.monotonic()

        try:
            async with self._semaphore:
                stream = await self.agent.run(prompt, context=context)
                text_parts = []
                async for event in stream:
                    if hasattr(event, "type") and event.type == "text" and event.content:
                        text_parts.append(event.content)
                    elif hasattr(event, "type") and event.type == "error":
                        log_data(logger, logging.WARNING, f"Worker error: {event.content}",
                                 data={"agent_id": self.agent_id, "task_id": task_id})
                result = "".join(text_parts)

            duration = time.monotonic() - start
            self.tasks_completed += 1
            self.total_duration_s += duration
            log_data(logger, logging.DEBUG, f"Worker completed task in {duration:.2f}s",
                     data={"agent_id": self.agent_id, "duration": duration})
            return result

        except Exception as e:
            self.state = "error"
            log_data(logger, logging.WARNING, f"Worker failed: {e}",
                     data={"agent_id": self.agent_id, "task_id": task_id})
            raise
        finally:
            self.state = "idle"
            self.current_task = None

    @property
    def avg_duration_s(self) -> float:
        if self.tasks_completed == 0:
            return 0.0
        return self.total_duration_s / self.tasks_completed

    def stats(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "state": self.state,
            "tasks_completed": self.tasks_completed,
            "avg_duration_s": round(self.avg_duration_s, 3),
            "total_duration_s": round(self.total_duration_s, 3),
            "current_task": self.current_task,
        }


class WorkerPool(BaseModel):
    """Pool of workers for concurrent agent execution.

    Distributes tasks across workers, with optional queue for backpressure.

    Usage:
        pool = WorkerPool(workers=4)
        pool.register("assistant", my_agent)
        result = await pool.run("assistant", "Hello!")
    """

    workers: dict[str, Worker] = Field(default_factory=dict)
    max_workers: int = Field(default=10)

    model_config = {"arbitrary_types_allowed": True}

    def register(self, agent_id: str, agent: Any, max_concurrent: int = 1) -> Worker:
        """Register an agent as a worker.

        Args:
            agent_id: Unique identifier for the agent.
            agent: The ChainForge Agent instance.
            max_concurrent: Max concurrent executions for this agent.

        Returns:
            The created Worker.
        """
        if len(self.workers) >= self.max_workers:
            raise ValueError(f"Max workers ({self.max_workers}) reached")
        worker = Worker(agent_id=agent_id, agent=agent, max_concurrent=max_concurrent)
        self.workers[agent_id] = worker
        log_data(logger, logging.INFO, f"Registered worker: {agent_id}")
        return worker

    def unregister(self, agent_id: str) -> None:
        """Remove a worker from the pool."""
        self.workers.pop(agent_id, None)

    async def run(self, agent_id: str, prompt: str, context: dict | None = None) -> str:
        """Execute an agent by ID.

        Args:
            agent_id: The registered agent identifier.
            prompt: Input prompt.
            context: Optional context.

        Returns:
            Agent's text output.

        Raises:
            KeyError: Agent not found in pool.
        """
        worker = self.workers.get(agent_id)
        if worker is None:
            raise KeyError(f"Agent '{agent_id}' not found. Registered: {list(self.workers.keys())}")
        return await worker.run(prompt, context=context)

    async def run_all(self, prompt: str, context: dict | None = None) -> dict[str, str]:
        """Execute all registered agents with the same prompt (parallel).

        Args:
            prompt: Input prompt for all agents.
            context: Optional context.

        Returns:
            Dict of {agent_id: output_text}.
        """
        tasks = {
            aid: worker.run(prompt, context=context)
            for aid, worker in self.workers.items()
        }
        results = {}
        for aid, coro in tasks.items():
            try:
                results[aid] = await coro
            except Exception as e:
                results[aid] = f"Error: {e}"
        return results

    def get_worker(self, agent_id: str) -> Worker | None:
        return self.workers.get(agent_id)

    def stats(self) -> list[dict[str, Any]]:
        return [w.stats() for w in self.workers.values()]

    @property
    def total_tasks_completed(self) -> int:
        return sum(w.tasks_completed for w in self.workers.values())

    @property
    def busy_workers(self) -> int:
        return sum(1 for w in self.workers.values() if w.state == "busy")
