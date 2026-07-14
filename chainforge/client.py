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
"""ChainForge HTTP Client — 远程调用 Agent 的 Python 客户端。

通过 HTTP API 连接到 ChainForge Server，支持同步和异步调用。

Usage:
    # 连接到远程
    client = ChainForgeClient("http://localhost:8000")

    # 同步调用
    result = client.run("my_agent", "Weather in Beijing?")
    print(result.output)

    # 异步流式调用
    async for event in client.stream("my_agent", "Tell me a story"):
        if event["type"] == "text":
            print(event["content"], end="")
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any


class ChainForgeClient:
    """HTTP client for remote ChainForge agents.

    Args:
        base_url: Server URL (e.g. "http://localhost:8000").
        api_key: Optional API key (sent as Bearer token).
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ── Sync API ─────────────────────────────────────────────────────────

    def run(self, agent_id: str, prompt: str = "", **kwargs) -> AgentResult:
        """Run an agent and return the full result (synchronous).

        Args:
            agent_id: Registered agent ID.
            prompt: Input prompt.
            **kwargs: Additional options (context, response_model).

        Returns:
            AgentResult with output, duration, tool calls, events.
        """
        import httpx

        headers = self._headers()
        body: dict[str, Any] = {"prompt": prompt, **kwargs}

        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post(f"/api/v1/agents/{agent_id}/run", json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return AgentResult(
                output=data.get("output", ""),
                duration_s=data.get("duration_s", 0.0),
                tool_calls=data.get("tool_calls", 0),
                events=data.get("events", []),
            )

    def health(self) -> dict:
        """Check server health."""
        import httpx

        with httpx.Client(base_url=self.base_url, timeout=10) as client:
            resp = client.get("/api/v1/health", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def info(self, agent_id: str) -> dict:
        """Get agent information."""
        import httpx

        with httpx.Client(base_url=self.base_url, timeout=10) as client:
            resp = client.get(f"/api/v1/agents/{agent_id}", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    # ── Async / Stream API ───────────────────────────────────────────────

    async def run_async(self, agent_id: str, prompt: str = "", **kwargs) -> AgentResult:
        """Run an agent and return the full result (asynchronous)."""
        import httpx

        body: dict[str, Any] = {"prompt": prompt, **kwargs}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            resp = await client.post(f"/api/v1/agents/{agent_id}/run", json=body, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            return AgentResult(
                output=data.get("output", ""),
                duration_s=data.get("duration_s", 0.0),
                tool_calls=data.get("tool_calls", 0),
                events=data.get("events", []),
            )

    async def stream(self, agent_id: str, prompt: str = "") -> AsyncIterator[dict]:
        """Stream agent events via SSE (asynchronous).

        Yields dicts with keys: type, content, data.

        Example:
            async for event in client.stream("agent", "Hello"):
                if event["type"] == "text":
                    print(event["content"], end="")
        """
        import httpx

        params = {"prompt": prompt}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            async with client.stream(
                "GET",
                f"/api/v1/agents/{agent_id}/run/stream",
                params=params,
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            event_data = json.loads(data_str)
                            yield event_data
                        except json.JSONDecodeError:
                            pass

    def _headers(self) -> dict[str, str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class AgentResult:
    """Result of a remote agent execution."""

    def __init__(self, output: str, duration_s: float, tool_calls: int, events: list[dict]):
        self.output = output
        self.duration_s = duration_s
        self.tool_calls = tool_calls
        self.events = events

    def __repr__(self) -> str:
        return (
            f"AgentResult(output={self.output[:60]}..., "
            f"duration={self.duration_s}s, "
            f"tool_calls={self.tool_calls})"
        )
