"""A2A protocol server — implement the Agent-to-Agent HTTP endpoints.

Implements the six standard A2A JSON-RPC endpoints:
  - agent-card        GET  /a2a/agent-card
  - task-send         POST /a2a/task-send
  - task-get          POST /a2a/task-get
  - task-cancel       POST /a2a/task-cancel
  - task-subscribe    POST /a2a/task-subscribe (SSE)
  - task-resubscribe  POST /a2a/task-resubscribe (SSE)

Usage:
    from chainforge.a2a.server import A2ARouter
    from chainforge.a2a.card import build_agent_card

    card = build_agent_card(my_agent, name="assistant", url="http://...")
    router = A2ARouter(card)
    router.register_agent("default", my_agent)

    # Mount in FastAPI
    app.include_router(router.get_fastapi_router())
"""

from __future__ import annotations

import asyncio
import datetime
import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from chainforge.a2a.types import (
    A2AResponse,
    Artifact,
    Message,
    Task,
    TaskCancelResult,
    TaskGetResult,
    TaskIdResubscribeParams,
    TaskQuery,
    TaskSendParams,
    TaskSendResult,
    TaskState,
    TaskStatus,
    make_artifact,
    make_message,
    make_task,
)
from chainforge.a2a.card import build_agent_card, AgentCard
from chainforge.core.stream import EventType
from chainforge.logging import get_logger

logger = get_logger("a2a.server")


# ── In-memory task store ───────────────────────────────────────────────────


class TaskStore:
    """Simple in-memory task store for A2A tasks."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def set(self, task: Task):
        self._tasks[task.id] = task

    def update_state(
        self,
        task_id: str,
        state: TaskState,
        message: str | None = None,
        artifacts: list[Artifact] | None = None,
        history: list[Message] | None = None,
    ) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        msg_obj = make_message("agent", message) if message else None
        task.status = TaskStatus(state=state, message=msg_obj, timestamp=now)
        if artifacts:
            task.artifacts.extend(artifacts)
        if history:
            task.history.extend(history)
        self._tasks[task_id] = task
        return task

    def list_active(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status.state in (TaskState.submitted, TaskState.working)]


# ── Agent wrapper for A2A ──────────────────────────────────────────────────


class A2AAgentWrapper:
    """Wraps a ChainForge Agent so it can be executed via the A2A protocol."""

    def __init__(self, agent: Any):
        self._agent = agent

    @property
    def agent(self) -> Any:
        return self._agent

    async def run(self, task: Task, message: Message) -> AsyncIterator[tuple]:
        """Run the agent on the given message and yield state updates.

        Yields (state, content, artifacts_list) tuples.
        """
        prompt_parts = []
        for part in message.parts:
            if part.text:
                prompt_parts.append(part.text)
            elif part.data:
                prompt_parts.append(json.dumps(part.data, ensure_ascii=False))
        prompt = "\n".join(prompt_parts) or "Hello"

        yield (TaskState.working, None, None)

        try:
            if hasattr(self._agent, "run"):
                result = await self._agent.run(prompt)
                if hasattr(result, "__aiter__"):
                    text_parts = []
                    async for event in result:
                        if event.type == EventType.text and event.content:
                            text_parts.append(event.content)
                        elif event.type == EventType.tool_call:
                            name = event.data.get("name", "unknown") if event.data else "unknown"
                            text_parts.append(f"\n[Tool: {name}]\n")
                        elif event.type == EventType.tool_result:
                            c = event.content or ""
                            text_parts.append(f"[Result: {c[:80]}]\n")
                        elif event.type == EventType.error:
                            yield (TaskState.failed, f"Agent error: {event.content}", None)
                            return

                    full = "".join(text_parts)
                    arts = [make_artifact("output", full)] if full else []
                    yield (TaskState.completed, full, arts)
                else:
                    text = str(result)
                    yield (TaskState.completed, text, [make_artifact("output", text)])
            else:
                text = str(self._agent)
                yield (TaskState.completed, text, [make_artifact("output", text)])
        except Exception as e:
            logger.error(f"A2A agent execution failed: {e}")
            yield (TaskState.failed, f"Agent execution error: {e}", None)


# ── A2A Router ─────────────────────────────────────────────────────────────


class A2ARouter(BaseModel):
    """Implements the A2A protocol endpoints for one or more agents."""

    agent_card: AgentCard = Field(description="AgentCard advertised by this A2A endpoint")
    agents: dict[str, A2AAgentWrapper] = Field(default_factory=dict, description="Registered A2A agent wrappers")
    task_store: TaskStore = Field(default_factory=TaskStore, description="Task state store")
    default_agent_id: str | None = Field(default=None, description="Default agent for routing")

    model_config = {"arbitrary_types_allowed": True}

    def register_agent(self, agent_id: str, agent: Any):
        """Register a ChainForge Agent as an A2A agent."""
        wrapper = A2AAgentWrapper(agent) if not isinstance(agent, A2AAgentWrapper) else agent
        self.agents[agent_id] = wrapper
        logger.info(f"A2A agent registered: {agent_id}")

    def register_agents(self, **agents: Any):
        for aid, agent in agents.items():
            self.register_agent(aid, agent)

    async def handle_agent_card(self) -> AgentCard:
        return self.agent_card

    async def handle_task_send(self, params: TaskSendParams) -> Task:
        task_id = params.id
        logger.info(f"task-send: id={task_id}, role={params.message.role}")

        existing = self.task_store.get(task_id)
        if existing:
            task = existing
            self.task_store.update_state(
                task_id, TaskState.working,
                message="Resuming with new input",
                history=[params.message],
            )
        else:
            task = make_task(
                task_id, state=TaskState.submitted,
                history=[params.message],
                session_id=params.session_id,
                metadata=params.metadata,
            )
            self.task_store.set(task)

        wrapper = self._resolve_agent(task)
        if wrapper is None:
            self.task_store.update_state(task_id, TaskState.failed, message="No agent registered")
            return self.task_store.get(task_id) or task

        asyncio.ensure_future(self._execute_task(wrapper, task_id, params))
        return self.task_store.get(task_id) or task

    async def handle_task_get(self, query: TaskQuery) -> Task:
        task = self.task_store.get(query.id)
        if task is None:
            return make_task(
                query.id, TaskState.failed,
                [make_message("agent", f"Task {query.id} not found")],
            )
        if query.history_length is not None and len(task.history) > query.history_length:
            task = task.model_copy(deep=True)
            task.history = task.history[-query.history_length:]
        return task

    async def handle_task_cancel(self, query: TaskQuery) -> Task:
        task = self.task_store.get(query.id)
        if task is None:
            return make_task(
                query.id, TaskState.canceled,
                [make_message("agent", f"Task {query.id} not found")],
            )
        self.task_store.update_state(query.id, TaskState.canceled, message="Canceled by user")
        return self.task_store.get(query.id) or task

    async def handle_task_subscribe(self, params: TaskSendParams) -> AsyncIterator[str]:
        task_id = params.id
        existing = self.task_store.get(task_id)
        if existing is None:
            task = make_task(task_id, state=TaskState.submitted, history=[params.message])
            self.task_store.set(task)
            wrapper = self._resolve_agent(task)
            if wrapper:
                asyncio.ensure_future(self._execute_task(wrapper, task_id, params))

        task_obj = self.task_store.get(task_id)
        if task_obj:
            yield f"data: {json.dumps({'type': 'task_update', 'task': task_obj.model_dump(mode='json')}, ensure_ascii=False)}\n\n"

        for _ in range(300):
            await asyncio.sleep(0.1)
            t = self.task_store.get(task_id)
            if t and t.status.state in (TaskState.completed, TaskState.failed, TaskState.canceled):
                yield f"data: {json.dumps({'type': 'task_complete', 'task': t.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
                return

    async def handle_task_resubscribe(self, params: TaskIdResubscribeParams) -> AsyncIterator[str]:
        task = self.task_store.get(params.id)
        if task is None:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Task {params.id} not found'}, ensure_ascii=False)}\n\n"
            return
        for msg in task.history:
            yield f"data: {json.dumps({'type': 'history', 'message': msg.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'task_complete', 'task': task.model_dump(mode='json')}, ensure_ascii=False)}\n\n"

    def _resolve_agent(self, task: Task) -> A2AAgentWrapper | None:
        agent_id = getattr(task.metadata or {}, "agent_id", self.default_agent_id)
        wrapper = self.agents.get(agent_id) if agent_id else None
        if wrapper is None and self.agents:
            wrapper = list(self.agents.values())[0]
        return wrapper

    async def _execute_task(self, wrapper: A2AAgentWrapper, task_id: str, params: TaskSendParams):
        try:
            final_state = TaskState.completed
            final_content = ""
            all_artifacts = []

            async for state, content, artifacts in wrapper.run(
                self.task_store.get(task_id) or make_task(task_id),
                params.message,
            ):
                if state == TaskState.working:
                    self.task_store.update_state(task_id, TaskState.working, message="Working...")
                elif state == TaskState.completed:
                    final_state = TaskState.completed
                    final_content = content or ""
                    all_artifacts = artifacts or []
                elif state == TaskState.failed:
                    final_state = TaskState.failed
                    final_content = content or "Unknown error"

            history_msg = make_message("agent", final_content) if final_content else None
            if history_msg:
                self.task_store.update_state(
                    task_id, final_state,
                    message=final_content,
                    artifacts=all_artifacts,
                    history=[history_msg],
                )
            else:
                self.task_store.update_state(task_id, final_state, artifacts=all_artifacts)

            logger.info(f"A2A task {task_id} -> {final_state.value}")
        except Exception as e:
            logger.error(f"A2A task {task_id} execution error: {e}")
            self.task_store.update_state(task_id, TaskState.failed, message=f"Execution error: {e}")

    def get_fastapi_router(self, prefix: str = "/a2a") -> Any:
        """Return a FastAPI APIRouter with A2A endpoints at *prefix*."""
        try:
            from fastapi import APIRouter, HTTPException
            from fastapi.responses import StreamingResponse
        except ImportError:
            raise ImportError("FastAPI required. Install: pip install 'chainforge[server]'")

        router = APIRouter(prefix=prefix, tags=["A2A"])
        a2a = self

        @router.get("/agent-card")
        async def get_agent_card():
            return await a2a.handle_agent_card()

        @router.post("/task-send", response_model=TaskSendResult)
        async def post_task_send(params: TaskSendParams):
            task = await a2a.handle_task_send(params)
            return TaskSendResult(task=task)

        @router.post("/task-get", response_model=TaskGetResult)
        async def post_task_get(query: TaskQuery):
            task = await a2a.handle_task_get(query)
            return TaskGetResult(task=task)

        @router.post("/task-cancel", response_model=TaskCancelResult)
        async def post_task_cancel(query: TaskQuery):
            task = await a2a.handle_task_cancel(query)
            return TaskCancelResult(task=task)

        @router.post("/task-subscribe")
        async def post_task_subscribe(params: TaskSendParams):
            return StreamingResponse(
                a2a.handle_task_subscribe(params),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        @router.post("/task-resubscribe")
        async def post_task_resubscribe(params: TaskIdResubscribeParams):
            return StreamingResponse(
                a2a.handle_task_resubscribe(params),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        return router


# ── Standalone A2A server factory ──────────────────────────────────────────


def create_a2a_app(
    agents: dict[str, Any] | None = None,
    *,
    card: AgentCard | None = None,
    agent_name: str = "ChainForgeAgent",
    agent_description: str = "A2A-capable agent powered by ChainForge",
    base_url: str = "http://localhost:8000",
    version: str = "1.0",
    streaming: bool = True,
) -> tuple[Any, A2ARouter]:
    """Create a FastAPI app pre-configured with A2A protocol support.

    Args:
        agents: Dict of {agent_id: agent_instance}.
        card: Pre-built AgentCard. Auto-built if None.
        agent_name: Name for auto-generated AgentCard.
        agent_description: Description for auto-generated AgentCard.
        base_url: Base URL for the agent endpoint.
        version: A2A spec version.
        streaming: SSE support flag.

    Returns:
        (FastAPI app, A2ARouter) tuple.
    """
    try:
        from fastapi import FastAPI
    except ImportError:
        raise ImportError("FastAPI required. Install: pip install 'chainforge[server]'")

    app = FastAPI(title="ChainForge A2A", version=version)

    if card is None:
        first = next(iter(agents.values())) if agents else None
        card = build_agent_card(
            first,
            name=agent_name,
            description=agent_description,
            url=f"{base_url}/a2a",
            version=version,
            streaming=streaming,
        )

    a2a_router = A2ARouter(agent_card=card)
    if agents:
        a2a_router.register_agents(**agents)

    app.include_router(a2a_router.get_fastapi_router())
    return app, a2a_router
