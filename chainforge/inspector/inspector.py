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
"""Agent Inspector — collect and expose agent execution data for debugging."""

from __future__ import annotations

import datetime
import json
import uuid
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("inspector")


class InspectionEvent(BaseModel):
    """A single recorded event from agent execution."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = Field(default="", description="Agent identifier")
    type: str = Field(default="state", description="Event type: state, text, tool_call, tool_result, error")
    state: str = Field(default="", description="Agent state at this event")
    iteration: int = Field(default=0, description="Agent loop iteration")
    content: str | None = Field(default=None, description="Event content")
    data: dict[str, Any] = Field(default_factory=dict, description="Event metadata")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    duration_ms: float = Field(default=0.0, description="Time since agent start")


class AgentInspection(BaseModel):
    """Inspection data for a single agent run."""

    agent_id: str = Field(default="")
    events: list[InspectionEvent] = Field(default_factory=list)
    start_time: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    end_time: str | None = Field(default=None)
    tool_call_count: int = Field(default=0)
    error_count: int = Field(default=0)
    total_iterations: int = Field(default=0)

    @property
    def duration_s(self) -> float:
        if self.end_time:
            start = datetime.datetime.fromisoformat(self.start_time)
            end = datetime.datetime.fromisoformat(self.end_time)
            return (end - start).total_seconds()
        return 0.0


class AgentInspector:
    """Collects and stores agent execution data for the inspector dashboard.

    This is a singleton-like registry — use the global ``inspector`` instance.

    Usage:
        from chainforge.inspector import inspector

        # Record an event (called by middleware or directly)
        inspector.record_event("agent-1", "state", state="thinking", iteration=1)

        # Query data
        events = inspector.get_events("agent-1")
        summary = inspector.get_summary("agent-1")
    """

    def __init__(self, max_events_per_agent: int = 10000):
        self._agents: dict[str, AgentInspection] = {}
        self._lock: Any = None
        self.max_events_per_agent = max_events_per_agent

    def start_run(self, agent_id: str) -> None:
        """Begin recording a new agent run."""
        self._agents[agent_id] = AgentInspection(agent_id=agent_id)
        logger.debug(f"Inspector: started recording {agent_id}")

    def record_event(
        self,
        agent_id: str,
        event_type: str,
        *,
        state: str = "",
        iteration: int = 0,
        content: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> InspectionEvent | None:
        """Record an execution event.

        Args:
            agent_id: The agent's identifier.
            event_type: Type of event (state, text, tool_call, tool_result, error).
            state: Current agent state.
            iteration: Agent loop iteration number.
            content: Event text content.
            data: Additional event metadata.

        Returns:
            The created InspectionEvent, or None if agent not tracked.
        """
        inspection = self._agents.get(agent_id)
        if inspection is None:
            return None

        # Calculate duration from start
        duration_ms = 0.0
        if inspection.start_time:
            start = datetime.datetime.fromisoformat(inspection.start_time)
            duration_ms = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds() * 1000

        event = InspectionEvent(
            agent_id=agent_id,
            type=event_type,
            state=state,
            iteration=iteration,
            content=content,
            data=data or {},
            duration_ms=round(duration_ms, 1),
        )

        inspection.events.append(event)

        # Track counters
        if event_type == "tool_call":
            inspection.tool_call_count += 1
        elif event_type == "error":
            inspection.error_count += 1
        inspection.total_iterations = max(inspection.total_iterations, iteration + 1)

        # Trim if over limit
        if len(inspection.events) > self.max_events_per_agent:
            inspection.events = inspection.events[-self.max_events_per_agent:]

        return event

    def end_run(self, agent_id: str) -> None:
        """Mark an agent run as complete."""
        inspection = self._agents.get(agent_id)
        if inspection:
            inspection.end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            logger.debug(f"Inspector: finished recording {agent_id}")

    def get_events(
        self,
        agent_id: str,
        *,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InspectionEvent]:
        """Get events for an agent, with optional filtering.

        Args:
            agent_id: The agent's identifier.
            event_type: Filter by event type (None = all).
            limit: Max events to return.
            offset: Number of events to skip.

        Returns:
            List of InspectionEvent, newest first.
        """
        inspection = self._agents.get(agent_id)
        if not inspection:
            return []

        events = inspection.events
        if event_type:
            events = [e for e in events if e.type == event_type]

        # Newest first, with offset and limit
        events = list(reversed(events))
        return events[offset:offset + limit]

    def get_summary(self, agent_id: str) -> dict[str, Any] | None:
        """Get a summary of the agent's execution.

        Returns:
            Dict with execution summary, or None if agent not found.
        """
        inspection = self._agents.get(agent_id)
        if not inspection:
            return None

        return {
            "agent_id": inspection.agent_id,
            "duration_s": round(inspection.duration_s, 2),
            "total_events": len(inspection.events),
            "tool_calls": inspection.tool_call_count,
            "errors": inspection.error_count,
            "iterations": inspection.total_iterations,
            "start_time": inspection.start_time,
            "end_time": inspection.end_time,
            "states": self._state_distribution(agent_id),
        }

    def _state_distribution(self, agent_id: str) -> dict[str, int]:
        """Count events by state."""
        inspection = self._agents.get(agent_id)
        if not inspection:
            return {}
        counts: dict[str, int] = defaultdict(int)
        for e in inspection.events:
            if e.state:
                counts[e.state] += 1
        return dict(counts)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all tracked agents with basic stats."""
        return [
            {
                "agent_id": aid,
                "events": len(a.event['events'] if isinstance(a, dict) and 'events' in a else a.events) if hasattr(a, 'events') else 0,
                "tool_calls": a['tool_call_count'] if isinstance(a, dict) else a.tool_call_count,
                "errors": a['error_count'] if isinstance(a, dict) else a.error_count,
                "start_time": a['start_time'] if isinstance(a, dict) else a.start_time,
                "end_time": a.get('end_time') if isinstance(a, dict) else a.end_time,
            }
            for aid, a in self._agents.items()
        ]

    def clear(self, agent_id: str | None = None) -> None:
        """Clear inspection data.

        Args:
            agent_id: Clear specific agent, or None to clear all.
        """
        if agent_id:
            self._agents.pop(agent_id, None)
        else:
            self._agents.clear()
        logger.debug(f"Inspector: cleared data for {agent_id or 'all agents'}")


# Global singleton instance
inspector = AgentInspector()
