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
"""Tests for the Durable Agent Execution module."""

import time

import pytest

from chainforge.enterprise.durable.handle import JobHandle
from chainforge.enterprise.durable.checkpoint import Checkpoint
from chainforge.enterprise.durable.dlq import DeadLetterQueue, DLQItem
from chainforge.enterprise.durable.journal import ExecutionJournal
from chainforge.enterprise.durable.recovery import CrashRecoveryPolicy
from chainforge.enterprise.durable.executor import DurableExecutor


class TestJobHandle:
    def test_default_state_is_queued(self):
        job = JobHandle(agent_id="agent-1", prompt="test prompt")
        assert job.status == "queued"
        assert job.progress == 0.0
        assert len(job.job_id) == 12


class TestCheckpoint:
    def test_serialization_via_to_json(self):
        cp = Checkpoint(
            job_id="job-001",
            step_index=3,
            total_steps=10,
            messages_json='[{"role":"user","content":"hello"}]',
            state_snapshot={"step": "processing"},
            tokens_used=500,
            cost_accumulated=0.015,
        )
        data = cp.to_json()
        assert data["job_id"] == "job-001"
        assert data["step_index"] == 3
        assert data["total_steps"] == 10
        assert data["tokens_used"] == 500


class TestDeadLetterQueue:
    def test_enqueue_list_discard_flow(self):
        dlq = DeadLetterQueue()
        assert dlq.count == 0

        item = dlq.enqueue(job_id="job-dead", step_index=2, reason="timeout")
        assert item.job_id == "job-dead"
        assert dlq.count == 1

        items = dlq.list()
        assert len(items) == 1

        discarded = dlq.discard("job-dead")
        assert discarded is True
        assert dlq.count == 0

    def test_discard_nonexistent(self):
        dlq = DeadLetterQueue()
        assert dlq.discard("ghost") is False


class TestExecutionJournal:
    def test_trace_returns_correct_steps(self):
        journal = ExecutionJournal()
        journal.record("job-a", 0, "started", detail="begin")
        journal.record("job-a", 1, "tool_call", detail="search_kb")
        journal.record("job-b", 0, "started", detail="begin b")

        trace = journal.trace("job-a")
        assert len(trace) == 2
        assert trace[0].job_id == "job-a"
        assert trace[1].event_type == "tool_call"

    def test_summary_computes_totals(self):
        journal = ExecutionJournal()
        journal.record("job-x", 0, "started", cost=0.01, tokens=100)
        journal.record("job-x", 1, "completed", cost=0.02, tokens=150)

        summary = journal.summary("job-x")
        assert summary["job_id"] == "job-x"
        assert summary["total_steps"] == 2
        assert summary["total_cost"] == 0.03
        assert summary["total_tokens"] == 250
        assert len(summary["events"]) == 2


class TestCrashRecoveryPolicy:
    def test_default_config(self):
        policy = CrashRecoveryPolicy()
        assert policy.auto_retry is True
        assert policy.max_retries == 3
        assert policy.resume_from == "last_checkpoint"
        assert policy.backoff_seconds == 5.0


class TestDurableExecutor:
    def test_stats_initially_empty(self):
        executor = DurableExecutor(backend="memory")
        stats = executor.stats()
        assert stats["total_jobs"] == 0
        assert stats["active"] == 0
        assert stats["completed"] == 0

    def test_submit_creates_job(self):
        import asyncio

        class StubAgent:
            identity = "agent-stub"

        async def _test():
            executor = DurableExecutor(backend="memory")
            job = await executor.submit(StubAgent(), "test prompt")
            assert job.status == "queued"
            assert job.agent_id == "agent-stub"
            assert job.prompt == "test prompt"

            stats = executor.stats()
            assert stats["total_jobs"] == 1

        asyncio.run(_test())
