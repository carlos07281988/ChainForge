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
"""Scheduler — cron-style scheduled agent execution.

Runs agents on a schedule using asyncio. No external dependencies.

Usage:
    from chainforge.scheduler import AgentScheduler
    from datetime import timedelta

    scheduler = AgentScheduler()
    scheduler.add_job("weather", my_agent, "Check weather",
                      interval=timedelta(hours=1))

    await scheduler.start()
    # ... runs in background ...
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from typing import Any

from chainforge.logging import get_logger

logger = get_logger("scheduler")


@dataclass
class ScheduledJob:
    """A scheduled agent job."""
    name: str
    agent: Any
    prompt: str
    interval_seconds: float
    last_run: float = 0.0
    run_count: int = 0
    last_result: str = ""
    error_count: int = 0


class AgentScheduler:
    """In-process scheduler that runs agents on a timer.

    Runs jobs in the background using asyncio.create_task.
    Supports add/remove/pause/resume and status reporting.
    """

    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def add_job(
        self,
        name: str,
        agent: Any,
        prompt: str,
        *,
        interval_seconds: float = 3600.0,
    ) -> "AgentScheduler":
        """Add a recurring agent job.

        Args:
            name: Job identifier.
            agent: ChainForge Agent instance.
            prompt: Prompt to run the agent with.
            interval_seconds: How often to run (default 1 hour).
        """
        self._jobs[name] = ScheduledJob(
            name=name,
            agent=agent,
            prompt=prompt,
            interval_seconds=interval_seconds,
        )
        logger.info(f"Scheduled job '{name}' every {interval_seconds}s")
        return self

    def remove_job(self, name: str) -> None:
        self._jobs.pop(name, None)

    def get_job(self, name: str) -> ScheduledJob | None:
        return self._jobs.get(name)

    def list_jobs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": j.name,
                "interval_s": j.interval_seconds,
                "last_run": j.last_run,
                "run_count": j.run_count,
                "error_count": j.error_count,
                "last_result_preview": j.last_result[:100] if j.last_result else "",
            }
            for j in self._jobs.values()
        ]

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler started with {len(self._jobs)} jobs")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def run_once(self, name: str) -> str | None:
        """Run a job immediately, regardless of schedule."""
        job = self._jobs.get(name)
        if job is None:
            return None
        return await self._execute_job(job)

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = asyncio.get_event_loop().time()
            for job in self._jobs.values():
                if now - job.last_run >= job.interval_seconds or job.last_run == 0:
                    try:
                        await self._execute_job(job)
                    except Exception as e:
                        job.error_count += 1
                        logger.error(f"Scheduled job '{job.name}' failed: {e}")
                    job.last_run = now
            await asyncio.sleep(10)  # check every 10 seconds

    async def _execute_job(self, job: ScheduledJob) -> str:
        """Execute a single job and store the result."""
        logger.info(f"Running scheduled job '{job.name}'")
        if hasattr(job.agent, "run"):
            stream = await job.agent.run(job.prompt)
            parts: list[str] = []
            async for event in stream:
                if hasattr(event, "type") and event.type == "text" and event.content:
                    parts.append(event.content)
            result = "".join(parts)
        else:
            result = str(job.agent)
        job.run_count += 1
        job.last_result = result
        logger.info(f"Scheduled job '{job.name}' done ({len(result)} chars)")
        return result

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def job_count(self) -> int:
        return len(self._jobs)
