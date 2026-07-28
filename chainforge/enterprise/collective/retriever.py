# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""ExperienceRetriever — search and retrieve relevant past experiences."""
from __future__ import annotations
from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.memory import CollectiveMemory

class ExperienceRetriever:
    """Search shared memory for relevant past experiences.

    Usage:
        cm = CollectiveMemory()
        retriever = ExperienceRetriever(cm)
        similar = retriever.search("refund a customer order", limit=5)
    """

    def __init__(self, memory: CollectiveMemory):
        self._memory = memory

    def search(self, task: str, limit: int = 5,
               min_success_rate: float = 0.0) -> list[Experience]:
        """Find similar past experiences.

        Args:
            task: Current task description.
            limit: Max results.
            min_success_rate: Minimum success rate (0.0-1.0).

        Returns:
            Relevant past experiences, freshest first.
        """
        return self._memory.search(task, limit=limit, min_success_rate=min_success_rate)
