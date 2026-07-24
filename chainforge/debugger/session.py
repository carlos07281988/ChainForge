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
"""DebugSession — wraps Agent + TimeTravelDebugger for interactive debugging."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.agent import Agent
from chainforge.core.debugger import StepDebugger
from chainforge.core.message import Message
from chainforge.core.state import AgentState
from chainforge.core.stream import EventType, StreamEvent
from chainforge.core.time_travel import TimeTravelDebugger
from chainforge.logging import get_logger

logger = get_logger("debugger.session")


class SessionStatus(str, Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    error = "error"


class Breakpoint(BaseModel):
    """A breakpoint that pauses agent execution on a matching event."""
    id: str = Field(default_factory=lambda: f"bp_{uuid.uuid4().hex[:8]}")
    event_type: str = Field(description="Event type to pause on: tool_call, error, state, llm")
    condition: str | None = Field(default=None, description="Optional condition (e.g. tool name pattern)")
    enabled: bool = Field(default=True)

    def matches(self, event: StreamEvent) -> bool:
        if not self.enabled:
            return False
        if self.event_type == "tool_call" and event.type == EventType.tool_call:
            if self.condition:
                name = event.data.get("name", "")
                return self.condition.lower() in name.lower()
            return True
        if self.event_type == "error" and event.type == EventType.error:
            return True
        if self.event_type == "state" and event.type == EventType.state:
            if self.condition:
                state = event.data.get("state", "")
                return self.condition.lower() in state.lower()
            return True
        if self.event_type == "llm" and event.type == EventType.text and not event.data:
            return True
        return False


class DebugSession(BaseModel):
    """Manages one interactive debug session for an Agent.

    Wraps an Agent with TimeTravelDebugger and provides:
      - Pause/resume/step control
      - Checkpoint browsing
      - Breakpoint management
      - Real-time event streaming

    Usage:
        session = DebugSession(agent=my_agent, name="my-debug")
        session.add_breakpoint(Breakpoint(event_type="tool_call", condition="weather"))
        async for event in session.run("What's the weather?"):
            # events stream in real-time - UI updates via WebSocket
            ...

        # Later: inspect checkpoints
        checkpoints = session.list_checkpoints()
        state = session.get_checkpoint_state(checkpoints[0])
    """

    model_config = {"arbitrary_types_allowed": True}

    id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:12]}")
    name: str = Field(default="debug-session")
    agent: Any = Field(default=None, description="The Agent being debugged")
    status: SessionStatus = Field(default=SessionStatus.pending)
    created_at: float = Field(default_factory=time.time)
    breakpoints: list[Breakpoint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        if "agent" not in data:
            data["agent"] = None
        super().__init__(**data)
        self._debugger: TimeTravelDebugger | None = None
        self._events: list[StreamEvent] = []
        self._pending_pause = False
        self._step_mode = False

    # ── Breakpoint management ──────────────────────────────────────────

    def add_breakpoint(self, bp: Breakpoint) -> Breakpoint:
        self.breakpoints.append(bp)
        return bp

    def remove_breakpoint(self, bp_id: str) -> bool:
        for i, bp in enumerate(self.breakpoints):
            if bp.id == bp_id:
                self.breakpoints.pop(i)
                return True
        return False

    def toggle_breakpoint(self, bp_id: str) -> Breakpoint | None:
        for bp in self.breakpoints:
            if bp.id == bp_id:
                bp.enabled = not bp.enabled
                return bp
        return None

    # ── Event stream (for WebSocket broadcasting) ───────────────────────

    @property
    def events(self) -> list[StreamEvent]:
        return list(self._events)

    @property
    def debugger(self) -> TimeTravelDebugger | None:
        return self._debugger

    def _should_pause(self, event: StreamEvent) -> bool:
        if self._pending_pause:
            self._pending_pause = False
            return True
        if self._step_mode and event.type in (EventType.tool_call, EventType.error):
            return True
        for bp in self.breakpoints:
            if bp.matches(event):
                return True
        return False

    # ── Agent execution with debugger ───────────────────────────────────

    def pause(self) -> None:
        """Request pause at the next event."""
        self._pending_pause = True

    def step(self) -> None:
        """Enable step mode: pause at next tool_call or error."""
        self._step_mode = True
        self._pending_pause = True

    def resume(self) -> None:
        """Resume normal execution."""
        self._step_mode = False
        self._pending_pause = False

    async def run(self, prompt: str | list[Message],
                   context: dict[str, Any] | None = None,
                   event_callback: callable | None = None) -> AsyncIterator[StreamEvent]:
        """Run the agent with debugging enabled.

        Args:
            prompt: User prompt or messages.
            context: Optional context dict.
            event_callback: Called for each event (for WebSocket broadcasting).

        Yields:
            StreamEvents for UI consumption.
        """
        self._debugger = TimeTravelDebugger(self.agent, max_checkpoints=100)
        self.status = SessionStatus.running
        self._events.clear()

        debug_stream = await self._debugger.run(prompt, context=context)

        try:
            async for event in debug_stream:
                self._events.append(event)

                # Check breakpoints / pause
                if self._should_pause(event):
                    self.status = SessionStatus.paused
                    yield event
                    # Wait for resume
                    while self.status == SessionStatus.paused:
                        await asyncio.sleep(0.05)
                    self.status = SessionStatus.running
                else:
                    yield event

                # Notify callback (WebSocket broadcast)
                if event_callback:
                    await event_callback(event)

            self.status = SessionStatus.completed
        except Exception as e:
            self.status = SessionStatus.error
            logger.error(f"Debug session failed: {e}")
            raise

        yield StreamEvent(type=EventType.done)

    # ── Checkpoint inspection ──────────────────────────────────────────

    def list_checkpoints(self) -> list[str]:
        if self._debugger is None:
            return []
        return list(self._debugger.checkpoints.keys())

    def get_checkpoint_state(self, checkpoint_id: str) -> dict[str, Any] | None:
        if self._debugger is None:
            return None
        return self._debugger.get_checkpoint(checkpoint_id)

    def get_checkpoint_messages(self, checkpoint_id: str) -> list[Message] | None:
        if self._debugger is None:
            return None
        state = self._debugger.get_checkpoint(checkpoint_id)
        if state is None:
            return None
        return state.get("messages")

    def get_checkpoint_context(self, checkpoint_id: str) -> dict[str, Any] | None:
        if self._debugger is None:
            return None
        state = self._debugger.get_checkpoint(checkpoint_id)
        if state is None:
            return None
        return state.get("context")

    # ── Provenance ─────────────────────────────────────────────────────

    def provenance_graph(self) -> dict[str, Any]:
        if self._debugger is None:
            return {}
        return self._debugger.provenance_graph()

    def trace_decision(self, event_id: str) -> list[dict[str, Any]]:
        if self._debugger is None:
            return []
        return self._debugger.trace_decision(event_id)

    # ── Summary ────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "event_count": len(self._events),
            "checkpoint_count": len(self.list_checkpoints()),
            "breakpoints": len(self.breakpoints),
            "duration_seconds": time.time() - self.created_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "breakpoints": [bp.model_dump() for bp in self.breakpoints],
            "event_count": len(self._events),
            "checkpoint_count": len(self.list_checkpoints()),
            "metadata": self.metadata,
        }
