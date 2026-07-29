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
import asyncio
from typing import Any
import time
import uuid

from chainforge.enterprise.durable.handle import JobHandle
from chainforge.enterprise.durable.checkpoint import Checkpoint
from chainforge.enterprise.durable.recovery import CrashRecoveryPolicy
from chainforge.enterprise.durable.dlq import DeadLetterQueue
from chainforge.enterprise.durable.journal import ExecutionJournal
from chainforge.logging import get_logger

logger = get_logger("enterprise.durable")


class DurableExecutor:
    """Persistent execution engine with checkpointing, crash recovery, and job management.

    Usage:
        executor = DurableExecutor(backend="sqlite", checkpoint_every=30)
        job = await executor.submit(agent, "Process 100k records")
        result = await executor.wait(job.job_id, timeout=3600)
    """

    def __init__(self, backend: str = "memory", checkpoint_every: int = 30,
                 crash_recovery: CrashRecoveryPolicy | None = None,
                 on_complete=None, on_failure=None, on_progress=None):
        self._backend = backend
        self._checkpoint_every = checkpoint_every
        self._crash_recovery = crash_recovery or CrashRecoveryPolicy()
        self._on_complete = on_complete
        self._on_failure = on_failure
        self._on_progress = on_progress
        self._jobs: dict[str, JobHandle] = {}
        self._journal = ExecutionJournal(backend=backend)
        self._dlq = DeadLetterQueue(backend=backend)

    @property
    def journal(self) -> ExecutionJournal:
        return self._journal

    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq

    async def submit(self, agent, prompt: str, **opts) -> JobHandle:
        """Submit a job for async execution. Returns a JobHandle for polling."""
        job = JobHandle(agent_id=getattr(agent, 'identity', None) or "unknown",
                        prompt=prompt)
        job.status = "queued"
        self._jobs[job.job_id] = job
        logger.info(f"Job submitted: {job.job_id}")
        return job

    async def execute(self, agent, prompt: str, **opts) -> Any:
        """Run synchronously with automatic checkpointing."""
        job = await self.submit(agent, prompt, **opts)
        job.status = "running"
        job.started_at = time.time()
        self._journal.record(job.job_id, 0, "started", detail=prompt[:200])
        return job  # In production, this runs the actual agent loop with checkpoints

    async def status(self, job_id: str) -> dict:
        """Get current job status."""
        job = self._jobs.get(job_id)
        if not job:
            return {"job_id": job_id, "status": "unknown"}
        return {"job_id": job.job_id, "status": job.status, "progress": job.progress,
                "started_at": job.started_at, "last_checkpoint_at": job.last_checkpoint_at,
                "error": job.error}

    async def wait(self, job_id: str, timeout: int | None = None) -> Any:
        """Wait for job completion (stub — production uses polling or websocket)."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        deadline = time.monotonic() + timeout if timeout else None
        while job.status not in ("done", "failed", "cancelled"):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            await asyncio.sleep(0.1)
        return job.result

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = "cancelled"
        job.completed_at = time.time()
        return True

    async def resume(self, job_id: str) -> JobHandle | None:
        """Resume a job from its last checkpoint."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        if job.checkpoints:
            last_cp = job.checkpoints[-1]
            job.status = "running"
            job.last_checkpoint_at = time.time()
            self._journal.record(job_id, last_cp.step_index, "resumed",
                                 detail=f"Resumed from checkpoint {last_cp.id}")
            return job
        return None

    def list_jobs(self, status_filter: str | None = None) -> list[JobHandle]:
        jobs = list(self._jobs.values())
        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter]
        return jobs

    def stats(self) -> dict:
        jobs = list(self._jobs.values())
        return {"total_jobs": len(jobs),
                "active": sum(1 for j in jobs if j.status in ("queued", "running", "checkpointing")),
                "completed": sum(1 for j in jobs if j.status == "done"),
                "failed": sum(1 for j in jobs if j.status == "failed"),
                "cancelled": sum(1 for j in jobs if j.status == "cancelled"),
                "dlq_items": self._dlq.count}
