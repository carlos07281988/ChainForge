# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Handoff data models — HandoffSLA and HandoffPackage."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class HandoffSLA:
    """Service-level agreement for a handoff."""

    response_time_minutes: int
    resolution_time_hours: int


class HandoffPackage:
    """A package of context for handing off from agent to human.

    Uses a regular (non-dataclass) class so the *field* ``summary`` and the
    *method* ``summary()`` can coexist — the field value is stored internally
    as ``_summary`` while the public ``summary()`` method returns a human-
    readable formatted string.
    """

    def __init__(
        self,
        run_id: str,
        summary: str,
        attempted_actions: list[str],
        failed_reason: str,
        relevant_context: dict,
        suggested_next_steps: list[str],
        priority: str = "medium",
        sla: HandoffSLA | None = None,
        created_at: float | None = None,
        agent_name: str = "",
        conversation: list[dict] | None = None,
    ):
        self.run_id = run_id
        self._summary = summary
        self.attempted_actions = attempted_actions
        self.failed_reason = failed_reason
        self.relevant_context = relevant_context
        self.suggested_next_steps = suggested_next_steps
        self.priority = priority
        self.sla = sla
        self.created_at = created_at if created_at is not None else time.time()
        self.agent_name = agent_name
        self.conversation = conversation if conversation is not None else []

    def summary(self) -> str:
        """Return a human-readable summary string."""
        return (
            f"[{self.priority.upper()}] {self._summary}\n"
            f"  Actions: {', '.join(self.attempted_actions)}\n"
            f"  Failed: {self.failed_reason}\n"
            f"  Next: {', '.join(self.suggested_next_steps)}\n"
            f"  Agent: {self.agent_name or 'unknown'} | Run: {self.run_id}"
        )

    def to_json(self) -> dict:
        """Serialize the handoff package to a JSON-compatible dict."""
        return {
            "run_id": self.run_id,
            "summary": self._summary,
            "attempted_actions": self.attempted_actions,
            "failed_reason": self.failed_reason,
            "relevant_context": self.relevant_context,
            "suggested_next_steps": self.suggested_next_steps,
            "priority": self.priority,
            "sla": {
                "response_time_minutes": self.sla.response_time_minutes,
                "resolution_time_hours": self.sla.resolution_time_hours,
            }
            if self.sla
            else None,
            "created_at": self.created_at,
            "agent_name": self.agent_name,
            "conversation": self.conversation,
        }
