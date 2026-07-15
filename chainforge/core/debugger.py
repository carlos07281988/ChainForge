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
"""StepDebugger — pause, inspect, and step through agent execution.

Wraps an Agent to provide step-by-step debugging:
  - Pause at each tool call, state transition, or LLM response
  - Inspect full state (messages, context, iteration)
  - Resume, step-over, or abort execution

Usage:
    from chainforge.core.debugger import StepDebugger

    agent = Agent(llm=llm, tools=[...])
    debug_agent = StepDebugger(agent)

    async for event in await debug_agent.run("Hello"):
        if debug_agent.paused:
            inp = input("Debug> ")
            if inp == "step": await debug_agent.step()
            elif inp == "continue": await debug_agent.resume()
            elif inp == "state": print(debug_agent.state_preview())
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("core.debugger")


class StepDebugger:
    """Wraps an Agent for step-by-step debugging.

    The debugger pauses execution at configurable breakpoints:
      - tool_call: before each tool execution
      - llm_response: after each LLM response
      - state_change: on every state transition

    While paused, you can inspect state, step, resume, or abort.

    Usage:
        debug = StepDebugger(agent, breakpoints=["tool_call", "llm_response"])
        stream = await debug.run("Hello")

        async for event in stream:
            if debug.paused:
                # Interactive inspection
                cmd = input("Debug> ")
                if cmd == "s": await debug.step()
                elif cmd == "c": await debug.resume()
                elif cmd == "q": await debug.abort()
                elif cmd == "state": print(debug.state_preview())
    """

    def __init__(
        self,
        agent: Agent,
        breakpoints: list[str] | None = None,
    ):
        self._agent = agent
        self._breakpoints = set(breakpoints or ["tool_call"])
        self._paused = False
        self._aborted = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._current_snapshot: dict[str, Any] = {}
        self._events_so_far: list[dict] = []
        self._step_mode = False

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def aborted(self) -> bool:
        return self._aborted

    def state_preview(self) -> str:
        """Return a human-readable summary of the current state."""
        snap = self._current_snapshot
        lines = [
            f"Iteration: {snap.get('iteration', '?')}",
            f"State: {snap.get('state', '?')}",
            f"Messages: {snap.get('message_count', 0)}",
        ]
        last_events = self._events_so_far[-3:] if self._events_so_far else []
        for ev in last_events:
            lines.append(f"  [{ev.get('type', '?')}] {ev.get('content', '')[:80]}")
        return "\n".join(lines)

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None) -> Stream:
        """Execute the agent with debugging hooks."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            self._aborted = False
            self._events_so_far = []

            # Yield debug start event
            yield StreamEvent(
                type=EventType.status,
                content="debug:start",
                data={"mode": "step_debug", "breakpoints": list(self._breakpoints)},
            )

            # Wrap the agent's stream
            stream = await self._agent.run(prompt, context=context)

            async for event in stream:
                if self._aborted:
                    yield StreamEvent(type=EventType.status, content="debug:aborted")
                    break

                # Record event
                ev_dict = {"type": event.type.value, "content": event.content, "data": event.data}
                self._events_so_far.append(ev_dict)

                # Update snapshot
                self._current_snapshot = {
                    "iteration": (event.data or {}).get("iteration", len(self._events_so_far)),
                    "state": (event.data or {}).get("state", event.type.value),
                    "message_count": len(self._events_so_far),
                    "last_event": event.type.value,
                }

                yield event

                # Check if we should pause at this event
                should_pause = False
                if event.type.value in self._breakpoints:
                    should_pause = True
                if self._step_mode:
                    should_pause = True
                    self._step_mode = False

                if should_pause and not self._aborted:
                    self._paused = True
                    self._pause_event.clear()
                    yield StreamEvent(
                        type=EventType.status,
                        content="debug:paused",
                        data={
                            "breakpoint": event.type.value,
                            "snapshot": self._current_snapshot,
                        },
                    )
                    # Wait for resume/step/abort
                    await self._pause_event.wait()
                    self._paused = False

            yield StreamEvent(type=EventType.status, content="debug:done")

        return Stream(_generate())

    async def step(self) -> None:
        """Step to the next event."""
        self._step_mode = True
        self._pause_event.set()

    async def resume(self) -> None:
        """Resume execution until next breakpoint."""
        self._step_mode = False
        self._pause_event.set()

    async def abort(self) -> None:
        """Abort execution."""
        self._aborted = True
        self._pause_event.set()

    def add_breakpoint(self, event_type: str) -> None:
        """Add a breakpoint event type."""
        self._breakpoints.add(event_type)

    def remove_breakpoint(self, event_type: str) -> None:
        """Remove a breakpoint event type."""
        self._breakpoints.discard(event_type)

    def set_breakpoints(self, event_types: list[str]) -> None:
        """Set the full list of breakpoint event types."""
        self._breakpoints = set(event_types)
