"""Agent Inspector — debug and monitor agent execution in real-time.

Provides:
  - Inspector singleton: collects agent execution events
  - API endpoints: query agent state, events, summaries
  - Dashboard page: browser-based inspector UI

Usage:
    from chainforge.inspector import inspector

    # Record events during agent execution
    inspector.start_run("agent-1")
    inspector.record_event("agent-1", "state", state="thinking", iteration=1)
    inspector.end_run("agent-1")

    # Query
    events = inspector.get_events("agent-1")
    summary = inspector.get_summary("agent-1")
"""

from chainforge.inspector.inspector import (
    AgentInspector,
    AgentInspection,
    InspectionEvent,
    inspector,
)

__all__ = [
    "AgentInspector",
    "AgentInspection",
    "InspectionEvent",
    "inspector",
]
