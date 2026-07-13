"""Agent state machine — explicit, observable state transitions.

States represent distinct phases of agent execution:
  initializing → thinking → [executing_tool → observing → thinking] → responding → done
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentState(str, Enum):
    """All possible states of an agent execution."""

    initializing = "initializing"
    thinking = "thinking"
    executing_tool = "executing_tool"
    observing = "observing"
    responding = "responding"
    error = "error"
    done = "done"


class StateTransition(BaseModel):
    """A single state transition with metadata."""

    from_state: AgentState | None = Field(default=None, description="Previous state")
    to_state: AgentState = Field(description="New state")
    iteration: int = Field(default=0, description="Current iteration")
    depth: int = Field(default=0, description="Nesting depth (for multi-agent)")
    tool_name: str | None = Field(default=None, description="Tool being executed, if applicable")
    message: str | None = Field(default=None, description="Human-readable status")
    timestamp: float = Field(default_factory=lambda: __import__("time").time())


class StateTracker:
    """Tracks agent state transitions and provides observable callbacks.

    Consumers can subscribe to state changes and react accordingly.
    """

    def __init__(self):
        self._current_state: AgentState = AgentState.initializing
        self._iteration: int = 0
        self._depth: int = 0
        self._history: list[StateTransition] = []
        self._listeners: list[Callable[[StateTransition], None]] = []

    @property
    def current_state(self) -> AgentState:
        return self._current_state

    @property
    def iteration(self) -> int:
        return self._iteration

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def history(self) -> list[StateTransition]:
        return list(self._history)

    def on_transition(self, listener: Callable[[StateTransition], None]) -> Callable:
        """Register a listener for state transitions. Returns an unregister function."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def transition(
        self,
        to_state: AgentState,
        *,
        tool_name: str | None = None,
        message: str | None = None,
        iteration: int | None = None,
        depth: int | None = None,
    ) -> StateTransition:
        """Transition to a new state and notify listeners.
        
        Args:
            to_state: Target state.
            tool_name: Optional tool name (for executing_tool state).
            message: Optional human-readable status message.
            iteration: Current loop iteration. If provided, updates internal counter.
            depth: Nesting depth for multi-agent scenarios.
        """
        old_state = self._current_state

        # Update internal counters when explicitly provided
        if iteration is not None:
            self._iteration = iteration
        if depth is not None:
            self._depth = depth

        t = StateTransition(
            from_state=old_state,
            to_state=to_state,
            iteration=self._iteration,
            depth=self._depth,
            tool_name=tool_name,
            message=message,
        )

        self._history.append(t)
        self._current_state = to_state

        for listener in self._listeners:
            listener(t)

        return t

    def reset(self) -> None:
        """Reset the tracker to initial state."""
        self._current_state = AgentState.initializing
        self._iteration = 0
        self._depth = 0
        self._history.clear()

    def to_stream_events(self):
        """Convert tracked history to StreamEvents for middleware consumption."""
        from chainforge.core.stream import EventType, StreamEvent
        events = []
        for t in self._history:
            data = {
                "state": t.to_state.value,
                "from_state": t.from_state.value if t.from_state else None,
                "iteration": t.iteration,
                "depth": t.depth,
            }
            if t.tool_name:
                data["tool_name"] = t.tool_name
            state_attr = getattr(EventType, "state", None)
            events.append(
                StreamEvent(
                    type=state_attr if state_attr else EventType.status,
                    content=t.message or t.to_state.value,
                    data=data,
                )
            )
        return events
