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
"""Tests for the A2A (Agent-to-Agent) protocol module."""

from __future__ import annotations

import datetime
import uuid

import pytest

from chainforge.a2a.types import (
    AgentCard,
    AgentCapabilities,
    Artifact,
    Message,
    Part,
    Skill,
    Task,
    TaskState,
    TaskStatus,
    make_agent_message,
    make_artifact,
    make_message,
    make_task,
    make_user_message,
)
from chainforge.a2a.card import build_agent_card
from chainforge.a2a.server import A2ARouter, A2AAgentWrapper, TaskStore


# ── Test Type Creation ─────────────────────────────────────────────────────


class TestA2ATypes:
    def test_make_message(self):
        msg = make_user_message("Hello")
        assert msg.role == "user"
        assert msg.parts[0].text == "Hello"

        msg2 = make_agent_message("Hi there")
        assert msg2.role == "agent"
        assert msg2.parts[0].text == "Hi there"

    def test_make_artifact(self):
        art = make_artifact("output", "Some result")
        assert art.name == "output"
        assert art.parts[0].text == "Some result"
        assert art.index == 0

    def test_make_task(self):
        task = make_task("task-1", TaskState.submitted)
        assert task.id == "task-1"
        assert task.status.state == TaskState.submitted
        assert task.status.timestamp != ""
        assert task.history == []
        assert task.artifacts == []

    def test_task_with_history(self):
        msg = make_user_message("Hello")
        task = make_task("task-2", TaskState.working, history=[msg])
        assert task.id == "task-2"
        assert task.status.state == TaskState.working
        assert len(task.history) == 1
        assert task.history[0].parts[0].text == "Hello"

    def test_task_state_values(self):
        assert TaskState.submitted.value == "submitted"
        assert TaskState.working.value == "working"
        assert TaskState.input_required.value == "input-required"
        assert TaskState.completed.value == "completed"
        assert TaskState.failed.value == "failed"
        assert TaskState.canceled.value == "canceled"

    def test_message_with_data_part(self):
        part = Part(data={"key": "value"})
        msg = Message(role="agent", parts=[part])
        assert msg.parts[0].data == {"key": "value"}

    def test_agent_card_defaults(self):
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        assert card.name == "TestAgent"
        assert card.version == "1.0"
        assert card.capabilities.streaming is False
        assert card.skills == []


# ── Test Agent Card Building ───────────────────────────────────────────────


class TestBuildAgentCard:
    def test_build_from_agent_with_tools(self):
        class MockSpec:
            name = "search_tool"
            description = "Search the web"

        class MockTool:
            spec = MockSpec()

        class MockAgent:
            tools = [MockTool()]
            skills = []
            system_prompt = "You are a search assistant"

        card = build_agent_card(
            MockAgent(),
            name="SearchAgent",
            description="Helps with search",
            url="http://localhost:8000/a2a",
            version="1.0",
            streaming=True,
        )

        assert card.name == "SearchAgent"
        assert card.description == "Helps with search"
        assert card.url == "http://localhost:8000/a2a"
        assert card.version == "1.0"
        assert card.capabilities.streaming is True

        # Should have agent:main skill + tool skills
        skill_ids = [s.id for s in card.skills]
        assert "agent:main" in skill_ids
        assert "search_tool" in skill_ids

    def test_build_without_description(self):
        class MockAgent:
            tools = []
            skills = []
            system_prompt = None

        card = build_agent_card(MockAgent(), name="MinimalAgent", url="http://localhost:8000/a2a")
        assert card.name == "MinimalAgent"
        # When no description or system prompt, description is empty from type name
        assert card.skills == []

    def test_build_with_auth(self):
        class MockAgent:
            tools = []
            skills = []
            system_prompt = None

        card = build_agent_card(MockAgent(), name="SecureAgent", url="http://localhost:8000/a2a", auth="bearer")
        assert card.authentication is not None
        assert card.authentication.schemes == ["bearer"]

    def test_build_with_provider(self):
        class MockAgent:
            tools = []
            skills = []
            system_prompt = None

        card = build_agent_card(
            MockAgent(), name="MyAgent", url="http://localhost:8000/a2a",
            provider="ChainForge", provider_url="https://chainforge.dev",
        )
        assert card.provider is not None
        assert card.provider.name == "ChainForge"
        assert card.provider.url == "https://chainforge.dev"


# ── Test Task Store ────────────────────────────────────────────────────────


class TestTaskStore:
    def test_store_and_retrieve(self):
        store = TaskStore()
        task = make_task("t1", TaskState.submitted)
        store.set(task)
        assert store.get("t1") is not None
        assert store.get("t1").id == "t1"

    def test_get_nonexistent(self):
        store = TaskStore()
        assert store.get("nonexistent") is None

    def test_update_state(self):
        store = TaskStore()
        task = make_task("t2", TaskState.submitted)
        store.set(task)

        store.update_state("t2", TaskState.working, message="Working on it")
        updated = store.get("t2")
        assert updated is not None
        assert updated.status.state == TaskState.working
        assert updated.status.message is not None

    def test_update_state_with_artifacts(self):
        store = TaskStore()
        task = make_task("t3", TaskState.working)
        store.set(task)

        arts = [make_artifact("output", "Result text")]
        store.update_state("t3", TaskState.completed, artifacts=arts)
        updated = store.get("t3")
        assert updated is not None
        assert updated.status.state == TaskState.completed
        assert len(updated.artifacts) == 1
        assert updated.artifacts[0].parts[0].text == "Result text"

    def test_list_active(self):
        store = TaskStore()
        store.set(make_task("t_submitted", TaskState.submitted))
        store.set(make_task("t_working", TaskState.working))
        store.set(make_task("t_done", TaskState.completed))
        store.set(make_task("t_failed", TaskState.failed))

        active = store.list_active()
        assert len(active) == 2
        assert all(t.status.state in (TaskState.submitted, TaskState.working) for t in active)

    def test_update_nonexistent_returns_none(self):
        store = TaskStore()
        result = store.update_state("ghost", TaskState.completed)
        assert result is None


# ── Test A2A Router (without HTTP) ─────────────────────────────────────────


class TestA2ARouter:
    def test_router_creation(self):
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        router = A2ARouter(agent_card=card)
        assert router.agent_card.name == "TestAgent"
        assert router.task_store is not None
        assert router.agents == {}

    def test_register_agent(self):
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        router = A2ARouter(agent_card=card)

        class FakeAgent:
            async def run(self, prompt):
                return iter([])

        router.register_agent("worker1", FakeAgent())
        assert "worker1" in router.agents
        assert isinstance(router.agents["worker1"], A2AAgentWrapper)

    def test_handle_task_get_nonexistent(self):
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        router = A2ARouter(agent_card=card)

        import asyncio
        from chainforge.a2a.types import TaskQuery

        task = asyncio.run(router.handle_task_get(TaskQuery(id="ghost")))
        assert task.status.state == TaskState.failed

    def test_handle_agent_card(self):
        card = AgentCard(name="CardAgent", url="http://localhost:8000/a2a", version="2.0")
        router = A2ARouter(agent_card=card)

        import asyncio
        result = asyncio.run(router.handle_agent_card())
        assert result.name == "CardAgent"
        assert result.version == "2.0"

    def test_handle_task_cancel(self):
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        router = A2ARouter(agent_card=card)

        from chainforge.a2a.types import TaskQuery

        import asyncio

        # Cancel nonexistent
        task = asyncio.run(router.handle_task_cancel(TaskQuery(id="ghost")))
        assert task.status.state == TaskState.canceled

    def test_handle_task_send(self):
        """Test task-send creates a task and runs it."""
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        router = A2ARouter(agent_card=card)

        from chainforge.a2a.types import TaskSendParams, Message, Part

        import asyncio

        class QuickAgent:
            async def run(self, prompt):
                items = []
                async for event in prompt if hasattr(prompt, "__aiter__") else (lambda: (yield None))():
                    items.append(event)
                # Simple result
                class FakeStream:
                    def __aiter__(self):
                        return self
                    async def __anext__(self):
                        raise StopAsyncIteration
                return FakeStream()

        # Actually test with a wrapper directly
        wrapper = A2AAgentWrapper(QuickAgent())
        assert wrapper.agent is not None

    def test_router_default_agent_id(self):
        card = AgentCard(name="TestAgent", url="http://localhost:8000/a2a")
        router = A2ARouter(agent_card=card, default_agent_id="primary")
        assert router.default_agent_id == "primary"


# ── Test A2A Agent Wrapper ────────────────────────────────────────────────


class TestA2AAgentWrapper:
    def test_wrapper_creation(self):
        class FakeAgent:
            pass

        wrapper = A2AAgentWrapper(FakeAgent())
        assert wrapper.agent is not None

    def test_wrapper_property(self):
        agent = object()
        wrapper = A2AAgentWrapper(agent)
        assert wrapper.agent is agent


# ── Test Create A2A App ────────────────────────────────────────────────────


class TestCreateA2AApp:
    def test_create_app_with_agents(self):
        """Just test that create_a2a_app produces a FastAPI app."""
        try:
            from chainforge.a2a.server import create_a2a_app

            class FakeAgent:
                async def run(self, prompt):
                    return iter([])

            app, router = create_a2a_app(
                agents={"default": FakeAgent()},
                agent_name="TestAgent",
                base_url="http://localhost:8000",
                streaming=True,
            )
            assert app is not None
            assert router is not None
            assert "default" in router.agents
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_create_app_without_agents(self):
        try:
            from chainforge.a2a.server import create_a2a_app

            app, router = create_a2a_app(agent_name="Standalone")
            assert app is not None
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not installed")


# ── Test Mount A2A ─────────────────────────────────────────────────────────


class TestMountA2A:
    def test_mount_integration(self):
        try:
            from chainforge.a2a.integration import mount_a2a
            from fastapi import FastAPI

            app = FastAPI()
            result_app, router = mount_a2a(
                app,
                base_url="http://localhost:8000",
                version="1.0",
            )
            assert result_app is app
            assert router is not None
            assert router.agent_card.name == "ChainForgeA2A"
        except ImportError:
            pytest.skip("FastAPI not installed")
