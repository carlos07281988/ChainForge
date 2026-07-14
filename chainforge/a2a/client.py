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
"""A2A protocol client — discover and call remote A2A agents.

Usage:
    from chainforge.a2a.client import A2AClient

    client = A2AClient()

    # Discover an agent's capabilities
    card = await client.get_agent_card("http://remote-host:8000/a2a")
    print(card.name, card.skills)

    # Send a task
    result = await client.send_task(
        "http://remote-host:8000/a2a",
        "task-123",
        "What is the weather in Beijing?",
    )
    print(result.task.status.state)
    print(result.task.artifacts[0].parts[0].text)

    # Stream a task
    async for event in client.subscribe_task(
        "http://remote-host:8000/a2a",
        "task-456",
        "Tell me a story",
    ):
        if event["type"] == "task_complete":
            print(event["task"]["artifacts"])
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from chainforge.a2a.types import (
    AgentCard,
    Task,
    TaskCancelResult,
    TaskGetResult,
    TaskQuery,
    TaskSendParams,
    TaskSendResult,
    Message,
    Part,
    PushNotificationConfig,
)
from chainforge.logging import get_logger

logger = get_logger("a2a.client")

DEFAULT_TIMEOUT = 120
"""Default HTTP request timeout in seconds."""


class A2AClient:
    """Client for communicating with A2A protocol servers.

    Wraps each standard A2A endpoint with a high-level method.
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, api_key: str | None = None):
        self.timeout = timeout
        self.api_key = api_key

    # ── Agent Card ─────────────────────────────────────────────────────────

    async def get_agent_card(self, base_url: str) -> AgentCard:
        """GET the AgentCard from an A2A agent endpoint.

        Args:
            base_url: Base URL of the A2A endpoint (e.g. http://host:8000/a2a).

        Returns:
            AgentCard with the agent's advertised capabilities.
        """
        url = self._url(base_url, "agent-card")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self._headers())
                resp.raise_for_status()
                return AgentCard(**resp.json())
        except ImportError:
            raise ImportError("httpx is required for A2A client. Install: pip install httpx")

    # ── Task Send ──────────────────────────────────────────────────────────

    async def send_task(
        self,
        base_url: str,
        task_id: str | None = None,
        message_text: str = "Hello",
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        push_url: str | None = None,
    ) -> TaskSendResult:
        """Send a task to an A2A agent and return the initial result.

        Args:
            base_url: A2A endpoint base URL.
            task_id: Client-generated task ID. Auto-generated if None.
            message_text: The message text to send.
            session_id: Optional session grouping ID.
            metadata: Optional metadata.
            push_url: Optional push notification URL.

        Returns:
            TaskSendResult containing the current task state.
        """
        params = TaskSendParams(
            id=task_id or str(uuid.uuid4()),
            session_id=session_id,
            message=Message(role="user", parts=[Part(text=message_text)]),
            metadata=metadata,
            push_notification=PushNotificationConfig(url=push_url) if push_url else None,
        )
        return await self._post(base_url, "task-send", params, TaskSendResult)

    async def send_task_with_message(
        self,
        base_url: str,
        task_id: str | None,
        message: Message,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskSendResult:
        """Send a task with a pre-built Message object."""
        params = TaskSendParams(
            id=task_id or str(uuid.uuid4()),
            session_id=session_id,
            message=message,
            metadata=metadata,
        )
        return await self._post(base_url, "task-send", params, TaskSendResult)

    # ── Task Get ───────────────────────────────────────────────────────────

    async def get_task(self, base_url: str, task_id: str, history_length: int | None = None) -> Task:
        """Get the current state of a task.

        Args:
            base_url: A2A endpoint base URL.
            task_id: Task ID to query.
            history_length: Max history messages to include.

        Returns:
            Task with current state.
        """
        query = TaskQuery(id=task_id, history_length=history_length)
        result = await self._post(base_url, "task-get", query, TaskGetResult)
        return result.task

    # ── Task Cancel ────────────────────────────────────────────────────────

    async def cancel_task(self, base_url: str, task_id: str) -> Task:
        """Cancel a running task.

        Args:
            base_url: A2A endpoint base URL.
            task_id: Task ID to cancel.

        Returns:
            Task in canceled state.
        """
        query = TaskQuery(id=task_id)
        result = await self._post(base_url, "task-cancel", query, TaskCancelResult)
        return result.task

    # ── Task Subscribe (SSE streaming) ─────────────────────────────────────

    async def subscribe_task(
        self,
        base_url: str,
        task_id: str | None = None,
        message_text: str = "Hello",
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to task execution via SSE streaming.

        Yields dict events with 'type' and payload keys.

        Args:
            base_url: A2A endpoint base URL.
            task_id: Task ID. Auto-generated if None.
            message_text: Initial message.
            session_id: Optional session ID.
            metadata: Optional metadata.
        """
        params = TaskSendParams(
            id=task_id or str(uuid.uuid4()),
            session_id=session_id,
            message=Message(role="user", parts=[Part(text=message_text)]),
            metadata=metadata,
        )
        url = self._url(base_url, "task-subscribe")

        import httpx
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=params.model_dump(mode="json"), headers=self._headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            yield json.loads(line[6:])
                        except json.JSONDecodeError:
                            pass

    # ── Task Resubscribe ───────────────────────────────────────────────────

    async def resubscribe_task(self, base_url: str, task_id: str, history_length: int | None = None) -> AsyncIterator[dict[str, Any]]:
        """Replay a completed task's history via SSE.

        Args:
            base_url: A2A endpoint base URL.
            task_id: Task ID to replay.
            history_length: Max history messages.

        Yields events with type 'history' or 'task_complete'.
        """
        from chainforge.a2a.types import TaskIdResubscribeParams

        params = TaskIdResubscribeParams(id=task_id, history_length=history_length)
        url = self._url(base_url, "task-resubscribe")

        import httpx
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=params.model_dump(mode="json"), headers=self._headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            yield json.loads(line[6:])
                        except json.JSONDecodeError:
                            pass

    # ── Internal HTTP helpers ──────────────────────────────────────────────

    async def _post(self, base_url: str, endpoint: str, params: Any, result_cls: type) -> Any:
        """POST to an A2A endpoint and deserialize the response."""
        import httpx

        url = self._url(base_url, endpoint)
        payload = params.model_dump(mode="json") if hasattr(params, "model_dump") else params

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        # If the response is wrapped in a result field (JSON-RPC style), unwrap it
        if isinstance(data, dict) and "result" in data:
            data = data["result"]

        if result_cls is not None and issubclass(result_cls, object):
            # Handle both dict responses and object-wrapped responses
            if isinstance(data, dict) and hasattr(result_cls, "model_validate"):
                return result_cls(**data)
            return data

        return data

    def _url(self, base_url: str, endpoint: str) -> str:
        base = base_url.rstrip("/")
        if not base.endswith("/a2a"):
            return f"{base}/a2a/{endpoint}"
        return f"{base}/{endpoint}"

    def _headers(self) -> dict[str, str]:
        hdrs = {"Content-Type": "application/json"}
        if self.api_key:
            hdrs["Authorization"] = f"Bearer {self.api_key}"
        return hdrs


# ── High-level convenience ──────────────────────────────────────────────────


class A2AAgentProxy:
    """A proxy that wraps a remote A2A agent as a callable object.

    The proxy can be used as a drop-in replacement for a local ChainForge Agent.
    When called, it sends a task to the remote agent and returns the result.

    Usage:
        proxy = A2AAgentProxy("http://remote:8000/a2a")
        result = await proxy.run("What's the weather?")
        print(result)
    """

    def __init__(self, base_url: str, agent_id: str | None = None, client: A2AClient | None = None):
        self.base_url = base_url
        self.agent_id = agent_id
        self._client = client or A2AClient()
        self._card: AgentCard | None = None

    async def discover(self) -> AgentCard:
        """Fetch and cache the remote agent's AgentCard."""
        if self._card is None:
            self._card = await self._client.get_agent_card(self.base_url)
        return self._card

    async def run(self, prompt: str | list | Message, **kwargs) -> str:
        """Run the remote agent with the given prompt.

        Args:
            prompt: Text prompt or Message object.
            **kwargs: Additional options (session_id, metadata).

        Returns:
            The agent's text output.
        """
        if isinstance(prompt, Message):
            result = await self._client.send_task_with_message(
                self.base_url, task_id=None, message=prompt, **kwargs
            )
        elif isinstance(prompt, list):
            msg = Message(role="user", parts=[Part(text=str(p)) for p in prompt])
            result = await self._client.send_task_with_message(
                self.base_url, task_id=None, message=msg, **kwargs
            )
        else:
            result = await self._client.send_task(
                self.base_url, task_id=None, message_text=str(prompt), **kwargs
            )

        # Poll for completion if still running
        task = result.task
        for _ in range(50):
            if task.status.state in ("completed", "failed", "canceled"):
                break
            import asyncio
            await asyncio.sleep(0.2)
            task = await self._client.get_task(self.base_url, task.id)

        # Extract text from artifacts
        texts = []
        for art in task.artifacts:
            for p in art.parts:
                if p.text:
                    texts.append(p.text)
        return "\n".join(texts)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Stream the remote agent's output via SSE."""
        async for event in self._client.subscribe_task(self.base_url, None, prompt):
            if event.get("type") == "task_update":
                task_data = event.get("task", {})
                for art in task_data.get("artifacts", []):
                    for p in art.get("parts", []):
                        if p.get("text"):
                            yield p["text"]
            elif event.get("type") == "task_complete":
                task_data = event.get("task", {})
                for art in task_data.get("artifacts", []):
                    for p in art.get("parts", []):
                        if p.get("text"):
                            yield p["text"]

    @property
    def name(self) -> str:
        return self._card.name if self._card else self.base_url

    @property
    def skills(self) -> list[dict]:
        return [s.model_dump() for s in self._card.skills] if self._card else []
