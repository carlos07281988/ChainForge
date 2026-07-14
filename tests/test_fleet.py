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
"""Tests for Fleet Management (worker pool and task queue)."""

import pytest
from chainforge.fleet import WorkerPool, TaskQueue, Task, TaskPriority


class TestWorkerPool:
    @pytest.mark.asyncio
    async def test_register_worker(self):
        pool = WorkerPool()

        class FakeAgent:
            async def run(self, prompt, context=None):
                class FakeStream:
                    def __aiter__(self):
                        return self
                    async def __anext__(self):
                        raise StopAsyncIteration
                return FakeStream()

        worker = pool.register("test-agent", FakeAgent())
        assert "test-agent" in pool.workers
        assert worker.agent_id == "test-agent"

    @pytest.mark.asyncio
    async def test_run_unknown_agent(self):
        pool = WorkerPool()
        with pytest.raises(KeyError):
            await pool.run("nonexistent", "Hello")

    @pytest.mark.asyncio
    async def test_unregister(self):
        pool = WorkerPool()

        class FakeAgent:
            async def run(self, prompt, context=None):
                class FakeStream:
                    def __aiter__(self):
                        return self
                    async def __anext__(self):
                        raise StopAsyncIteration
                return FakeStream()

        pool.register("test", FakeAgent())
        assert "test" in pool.workers
        pool.unregister("test")
        assert "test" not in pool.workers

    @pytest.mark.asyncio
    async def test_worker_stats(self):
        pool = WorkerPool()

        class FakeAgent:
            async def run(self, prompt, context=None):
                class FakeStream:
                    def __aiter__(self):
                        return self
                    async def __anext__(self):
                        raise StopAsyncIteration
                return FakeStream()

        pool.register("test", FakeAgent())
        stats = pool.stats()
        assert len(stats) == 1
        assert stats[0]["agent_id"] == "test"
        assert stats[0]["state"] == "idle"

    def test_max_workers(self):
        pool = WorkerPool(max_workers=2)

        class FakeAgent:
            pass

        pool.register("a1", FakeAgent())
        pool.register("a2", FakeAgent())
        with pytest.raises(ValueError):
            pool.register("a3", FakeAgent())

    def test_total_tasks_completed(self):
        pool = WorkerPool()

        class FakeAgent:
            pass

        pool.register("test", FakeAgent())
        assert pool.total_tasks_completed == 0

    def test_busy_workers(self):
        pool = WorkerPool()

        class FakeAgent:
            pass

        pool.register("test", FakeAgent())
        assert pool.busy_workers == 0


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_put_and_get(self):
        queue = TaskQueue()
        queue.put("agent-1", "Hello", priority=TaskPriority.high)
        task = await queue.get()
        assert task.agent_id == "agent-1"
        assert task.prompt == "Hello"
        assert task.priority == TaskPriority.high

    @pytest.mark.asyncio
    async def test_priority_order(self):
        queue = TaskQueue()
        queue.put("agent-1", "Low priority", priority=TaskPriority.low)
        queue.put("agent-1", "High priority", priority=TaskPriority.high)
        queue.put("agent-1", "Normal priority", priority=TaskPriority.normal)

        task1 = await queue.get()
        task2 = await queue.get()
        task3 = await queue.get()

        assert task1.priority == TaskPriority.high
        assert task2.priority == TaskPriority.normal
        assert task3.priority == TaskPriority.low

    def test_peek(self):
        queue = TaskQueue()
        assert queue.peek() is None
        queue.put("agent-1", "Test")
        task = queue.peek()
        assert task is not None
        assert task.prompt == "Test"
        assert queue.pending_count == 1

    def test_complete(self):
        queue = TaskQueue()
        task = queue.put("agent-1", "Test")
        assert queue.completed_count == 0
        queue.complete(task, result="Output")
        assert queue.completed_count == 1
        assert task.result == "Output"
        assert task.completed_at is not None
        assert task.duration_s >= 0

    def test_complete_with_error(self):
        queue = TaskQueue()
        task = queue.put("agent-1", "Test")
        queue.complete(task, error="Something went wrong")
        assert task.error == "Something went wrong"

    def test_stats(self):
        queue = TaskQueue()
        queue.put("agent-1", "Task 1")
        queue.put("agent-1", "Task 2")
        stats = queue.stats()
        assert stats["pending"] == 2
        assert stats["completed"] == 0

    def test_wait_time(self):
        import time
        queue = TaskQueue()
        task = queue.put("agent-1", "Test")
        time.sleep(0.05)
        assert task.wait_s > 0


class TestTask:
    def test_task_id_unique(self):
        t1 = Task(agent_id="a", prompt="p")
        t2 = Task(agent_id="a", prompt="p")
        assert t1.id != t2.id

    def test_task_defaults(self):
        t = Task(agent_id="a", prompt="p")
        assert t.priority == TaskPriority.normal
        assert t.result is None
        assert t.error is None
        assert t.completed_at is None

    def test_duration(self):
        import time
        t = Task(agent_id="a", prompt="p", created_at=time.time() - 5)
        t.completed_at = time.time()
        assert 4.0 < t.duration_s < 6.0
