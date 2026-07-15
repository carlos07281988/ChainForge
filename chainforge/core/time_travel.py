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
"""TimeTravelDebugger — record, replay, and branch agent execution.

Extends StepDebugger with checkpoint-based time travel:
  - Record: captures full execution snapshots at each step
  - Replay: rewind to any checkpoint and replay from there
  - Branch: fork execution from a specific checkpoint for comparison
  - Diff: compare state between two checkpoints
"""

from __future__ import annotations

import asyncio
import copy
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.state import StateTracker, InMemoryCheckpointer
from chainforge.core.stream import EventType, Stream, StreamEvent
from pydantic import BaseModel, Field

from chainforge.core.debugger import StepDebugger
from chainforge.logging import get_logger, log_data

logger = get_logger("core.time_travel")


class ExecutionCheckpoint(BaseModel):
    """A snapshot of execution state at a point in time."""

    id: str = Field(description="Checkpoint ID")
    timestamp: float = Field(default_factory=time.time)
    iteration: int = Field(default=0)
    state: str = Field(default="")
    messages_snapshot: list[dict] = Field(default_factory=list)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    event_log: list[dict] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimeTravelDebugger:
    """Record, replay, and branch agent execution.

    Wraps an Agent with comprehensive execution recording, enabling
    time-travel debugging capabilities.

    Usage:
        debugger = TimeTravelDebugger(agent)
        stream = await debugger.run("Hello")

        # Later: replay from checkpoint 3
        replay_stream = debugger.replay(checkpoint_id="ckp_3")
        async for event in replay_stream:
            ...

        # Fork a branch
        branch_stream = debugger.branch(checkpoint_id="ckp_3")
        async for event in branch_stream:
            ...

        # Show diff between checkpoints
        diff = debugger.diff("ckp_2", "ckp_5")
    """

    def __init__(
        self,
        agent: Agent,
        max_checkpoints: int = 100,
    ):
        self._agent = agent
        self._max_checkpoints = max_checkpoints
        self._checkpoints: dict[str, ExecutionCheckpoint] = {}
        self._checkpoint_list: list[str] = []  # ordered list of checkpoint IDs
        self._events: list[dict] = []
        self._last_snapshot: dict[str, Any] = {}

    @property
    def checkpoints(self) -> list[ExecutionCheckpoint]:
        """Return all checkpoints in order."""
        return [self._checkpoints[cid] for cid in self._checkpoint_list]

    @property
    def events(self) -> list[dict]:
        """Return all recorded events."""
        return list(self._events)

    def _record_checkpoint(
        self,
        iteration: int,
        state: str,
        messages: list,
        ctx: dict | None = None,
    ) -> str:
        """Record a checkpoint at the current execution point."""
        ckp_id = f"ckp_{iteration}_{len(self._checkpoint_list)}_{int(time.time() * 1000)}"

        msg_snapshot = []
        for m in messages:
            try:
                if hasattr(m, "model_dump"):
                    msg_snapshot.append(m.model_dump())
                elif hasattr(m, "dict"):
                    msg_snapshot.append(m.dict())
                else:
                    msg_snapshot.append({"content": str(m)})
            except Exception:
                msg_snapshot.append({"content": str(m)[:200]})

        checkpoint = ExecutionCheckpoint(
            id=ckp_id,
            iteration=iteration,
            state=state,
            messages_snapshot=msg_snapshot,
            context_snapshot=copy.deepcopy(ctx or {}),
            event_log=list(self._events[-20:]),  # last 20 events for context
            metadata={"total_events": len(self._events)},
        )

        self._checkpoints[ckp_id] = checkpoint
        self._checkpoint_list.append(ckp_id)

        # Prune if over limit
        if len(self._checkpoint_list) > self._max_checkpoints:
            old_id = self._checkpoint_list.pop(0)
            self._checkpoints.pop(old_id, None)

        return ckp_id

    async def run(
        self,
        prompt: str | list[Message],
        *,
        context: dict[str, Any] | None = None,
        auto_checkpoint: bool = True,
    ) -> Stream:
        """Execute the agent with full recording.

        Args:
            prompt: User prompt or messages.
            context: Optional context.
            auto_checkpoint: Automatically checkpoint at each state transition.
        """
        self._events = []
        self._checkpoints = {}
        self._checkpoint_list = []

        ctx = context or {}

        async def _generate() -> AsyncIterator[StreamEvent]:
            yield StreamEvent(
                type=EventType.status,
                content="time_travel:start",
                data={"mode": "recording", "max_checkpoints": self._max_checkpoints},
            )

            iteration = 0
            stream = await self._agent.run(prompt, context=ctx)

            async for event in stream:
                ev_dict = {"type": event.type.value, "content": event.content, "data": event.data}
                self._events.append(ev_dict)
                self._last_snapshot = {
                    "last_event": event.type.value,
                    "iteration": (event.data or {}).get("iteration", iteration),
                }

                yield event

                # Auto-checkpoint on state transitions and tool calls
                if auto_checkpoint and event.type in (EventType.state, EventType.tool_call):
                    iteration = (event.data or {}).get("iteration", iteration)
                    messages = ctx.get("_messages", [])
                    ckp_id = self._record_checkpoint(iteration, event.type.value, messages, ctx)
                    yield StreamEvent(
                        type=EventType.status,
                        content="time_travel:checkpoint",
                        data={"checkpoint_id": ckp_id, "iteration": iteration},
                    )

            yield StreamEvent(type=EventType.status, content="time_travel:done",
                              data={"checkpoints": len(self._checkpoints), "events": len(self._events)})

        return Stream(_generate())

    def replay(self, checkpoint_id: str) -> Stream:
        """Replay execution from a given checkpoint.

        Returns events that occurred between the checkpoint and the end of recording.
        """
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint '{checkpoint_id}' not found")

        ckp = self._checkpoints[checkpoint_id]
        ckp_index = self._checkpoint_list.index(checkpoint_id)

        # Find the event index corresponding to this checkpoint
        start_event_idx = ckp.metadata.get("total_events", 0)
        if start_event_idx >= len(self._events):
            # Estimate from checkpoint position
            fraction = ckp_index / max(len(self._checkpoint_list), 1)
            start_event_idx = int(len(self._events) * fraction)

        replay_events = self._events[start_event_idx:]

        async def _generate() -> AsyncIterator[StreamEvent]:
            yield StreamEvent(
                type=EventType.status,
                content="time_travel:replay",
                data={
                    "checkpoint_id": checkpoint_id,
                    "iteration": ckp.iteration,
                    "state": ckp.state,
                    "total_events": len(replay_events),
                },
            )
            for ev_dict in replay_events:
                yield StreamEvent(
                    type=EventType(ev_dict["type"]),
                    content=ev_dict.get("content"),
                    data=ev_dict.get("data", {}),
                )
            yield StreamEvent(type=EventType.status, content="time_travel:replay_done")

        return Stream(_generate())

    def branch(self, checkpoint_id: str) -> Stream:
        """Create a branch from a checkpoint.

        Returns the checkpoint's context as a Stream that can be fed
        into a new Agent run.
        """
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint '{checkpoint_id}' not found")

        ckp = self._checkpoints[checkpoint_id]

        async def _generate() -> AsyncIterator[StreamEvent]:
            yield StreamEvent(
                type=EventType.status,
                content="time_travel:branch",
                data={
                    "checkpoint_id": checkpoint_id,
                    "iteration": ckp.iteration,
                    "state": ckp.state,
                    "message_count": len(ckp.messages_snapshot),
                },
            )
            # Reconstruct messages from the checkpoint
            for msg_data in ckp.messages_snapshot:
                try:
                    from chainforge.core.message import Message as CfMessage
                    msg = CfMessage.model_validate(msg_data)
                    yield StreamEvent(
                        type=EventType.status,
                        content="message:restored",
                        data={"role": msg.role.value, "content": str(msg.content)[:200]},
                    )
                except Exception:
                    pass

            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def diff(self, checkpoint_id_a: str, checkpoint_id_b: str) -> dict[str, Any]:
        """Compare state between two checkpoints.

        Returns a dict describing what changed.
        """
        if checkpoint_id_a not in self._checkpoints:
            raise ValueError(f"Checkpoint '{checkpoint_id_a}' not found")
        if checkpoint_id_b not in self._checkpoints:
            raise ValueError(f"Checkpoint '{checkpoint_id_b}' not found")

        ckp_a = self._checkpoints[checkpoint_id_a]
        ckp_b = self._checkpoints[checkpoint_id_b]

        changes = {
            "iteration_delta": ckp_b.iteration - ckp_a.iteration,
            "state_a": ckp_a.state,
            "state_b": ckp_b.state,
            "event_count_a": len(ckp_a.event_log),
            "event_count_b": len(ckp_b.event_log),
            "context_keys_a": list(ckp_a.context_snapshot.keys()),
            "context_keys_b": list(ckp_b.context_snapshot.keys()),
            "messages_a": len(ckp_a.messages_snapshot),
            "messages_b": len(ckp_b.messages_snapshot),
            "new_context_keys": [
                k for k in ckp_b.context_snapshot if k not in ckp_a.context_snapshot
            ],
        }
        return changes

    def summary(self) -> dict[str, Any]:
        """Return a summary of the recording session."""
        return {
            "total_checkpoints": len(self._checkpoints),
            "total_events": len(self._events),
            "checkpoints": [
                {"id": ckp.id, "iteration": ckp.iteration, "state": ckp.state}
                for ckp in self.checkpoints
            ],
            "last_state": self._last_snapshot,
        }


