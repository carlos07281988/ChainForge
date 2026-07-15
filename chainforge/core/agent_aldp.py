# Copyright 2026 ChainForge Contributors
# AldpDebugSession — wraps Agent.run() to emit ALDP events for live debugging.

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from chainforge.aldp.server import ALDPServer
from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import Stream, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("core.agent_aldp")


class AldpDebugSession:
    """Wraps an Agent with ALDP live debugging support.

    Execution events are streamed to connected WebSocket clients in real-time.
    Clients can send pause/resume/step commands.

    Usage:
        session = AldpDebugSession(agent)
        stream = await session.run("Hello", aldp_port=9229)
    """

    def __init__(self, agent: Agent):
        self._agent = agent
        self._server: ALDPServer | None = None

    async def run(
        self,
        prompt: str | list[Message],
        *,
        aldp_host: str = "localhost",
        aldp_port: int = 9229,
        wait_for_client: bool = True,
        context: dict[str, Any] | None = None,
    ) -> Stream:
        """Execute the agent with ALDP live debugging.

        Args:
            prompt: User input.
            aldp_host: WebSocket server host.
            aldp_port: WebSocket server port (default 9229).
            wait_for_client: If True, wait for a WebSocket client before starting.
            context: Optional execution context.

        Returns:
            Stream of execution events.
        """
        self._server = ALDPServer(host=aldp_host, port=aldp_port)
        await self._server.start()

        if wait_for_client:
            conn = await self._server.wait_for_connection()
            if conn is None:
                logger.warning("ALDP: no client connected")
            else:
                logger.info("ALDP: client connected")

        async def _generate() -> AsyncIterator[StreamEvent]:
            server = self._server
            try:
                stream = await self._agent.run(prompt, context=context)
                async for event in stream:
                    if event.type.value == "state":
                        state = event.data.get("state", event.content or "")
                        iteration = event.data.get("iteration", 0)
                        await server.broadcast("state", {
                            "state": state, "iteration": iteration,
                            "node": event.data.get("node", ""),
                        })
                    elif event.type.value == "tool_call":
                        await server.broadcast("tool_call", {
                            "name": event.data.get("name", ""),
                            "args": event.data.get("args", {}),
                        })
                        await server.wait_if_paused()
                    elif event.type.value == "tool_result":
                        await server.broadcast("tool_result", {
                            "name": event.data.get("name", ""),
                            "content": (event.data.get("content") or "")[:500],
                            "is_error": event.data.get("is_error", False),
                        })
                    elif event.type.value == "text" and event.content:
                        await server.broadcast("llm_response", {
                            "content": event.content[:1000],
                        })
                    elif event.type.value == "error":
                        await server.broadcast("error", {"message": event.content or ""})
                    elif event.type.value == "done":
                        await server.broadcast("done", {"output": event.content or ""})
                    yield event
            except Exception as e:
                await server.broadcast("error", {"message": str(e)})
                yield StreamEvent.error(f"ALDP error: {e}")
            finally:
                await server.stop()

        return Stream(_generate())

    @property
    def server(self) -> ALDPServer | None:
        return self._server


__all__ = ["AldpDebugSession"]
