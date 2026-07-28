# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""ConflictResolver — find and resolve conflicting agent experiences."""
from __future__ import annotations
from collections import defaultdict
from pydantic import BaseModel, Field
from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.memory import CollectiveMemory
from chainforge.logging import get_logger

logger = get_logger("enterprise.collective.resolver")

class ConflictResolution(BaseModel):
    """A resolved conflict between agent experiences."""
    task_type: str = Field(description="The task type with conflicting experiences")
    agent_a_outcome: str = ""
    agent_b_outcome: str = ""
    resolution: str = ""
    recommendation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

class ConflictResolver:
    """Find conflicting experiences and generate resolutions.

    Usage:
        resolver = ConflictResolver(memory=cm)
        conflicts = resolver.find_conflicts()
        for c in conflicts:
            print(f"{c.task_type}: {c.recommendation} (confidence: {c.confidence})")
    """

    def __init__(self, memory: CollectiveMemory):
        self._memory = memory

    def find_conflicts(self) -> list[ConflictResolution]:
        """Find task types where agents have produced conflicting outcomes.

        Groups experiences by task_type, looks for success/failure
        contradictions, and recommends the higher-success-rate approach.

        Returns:
            List of ConflictResolution objects.
        """
        all_exp = self._memory.export(format="json")
        by_type: dict[str, list[dict]] = defaultdict(list)
        for e in all_exp:
            by_type[e.get("task_type", "general")].append(e)

        conflicts: list[ConflictResolution] = []
        for task_type, exps in by_type.items():
            if len(exps) < 2:
                continue
            successes = [e for e in exps if e.get("outcome") == "success"]
            failures = [e for e in exps if e.get("outcome") == "failure"]
            if successes and failures:
                # Recommend the tools used in successful runs
                success_tools: dict[str, int] = defaultdict(int)
                failure_tools: dict[str, int] = defaultdict(int)
                for e in successes:
                    for t in e.get("tools_used", []):
                        success_tools[t] += 1
                for e in failures:
                    for t in e.get("tools_used", []):
                        failure_tools[t] += 1

                # Tools that appear more in success vs failure
                recommended_tools = [
                    t for t, count in success_tools.items()
                    if count > failure_tools.get(t, 0)
                ]

                success_rate = len(successes) / len(exps)
                resolution = ConflictResolution(
                    task_type=task_type,
                    agent_a_outcome=f"success ({len(successes)} runs)",
                    agent_b_outcome=f"failure ({len(failures)} runs)",
                    resolution=f"Tools associated with success: {recommended_tools}" if recommended_tools else "No clear tool pattern",
                    recommendation=f"Prefer using: {', '.join(recommended_tools)}" if recommended_tools else "Insufficient data to recommend",
                    confidence=round(success_rate, 2),
                )
                conflicts.append(resolution)
                logger.info(f"Conflict found: {task_type} (confidence={success_rate:.2f})")

        return conflicts
