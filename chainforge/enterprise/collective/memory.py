# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""CollectiveMemory — shared experience pool for multiple agents."""
from __future__ import annotations
import time
from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.forgetting import ForgettingCurve
from chainforge.logging import get_logger

logger = get_logger("enterprise.collective")

class CollectiveMemory:
    """Shared experience pool for multiple agents.

    Agents record experiences after each run. New agents query relevant
    past experiences before starting. Experiences decay over time.

    Usage:
        cm = CollectiveMemory(namespace="customer-support")
        cm.add(Experience(id="1", task="refund order", task_type="refund", ...))
        results = cm.search("refund", limit=5, min_success_rate=0.5)
    """

    def __init__(self, backend: str = "memory", namespace: str = "default",
                 forgetting_curve: str = "ebbinghaus", half_life_days: float = 7.0):
        self._backend = backend
        self._namespace = namespace
        self._experiences: list[Experience] = []
        self._forgetting_curve = forgetting_curve
        self._half_life = half_life_days

    @property
    def namespace(self) -> str: return self._namespace

    def add(self, exp: Experience) -> None:
        """Add an experience to the shared pool."""
        self._experiences.append(exp)
        logger.debug(f"Experience recorded: {exp.id} ({exp.task_type})")

    def search(self, task_hint: str, limit: int = 5,
               min_success_rate: float = 0.0) -> list[Experience]:
        """Search for relevant past experiences.

        Uses keyword matching (production version would use embeddings).
        Results are scored by relevance x decay_factor.

        Args:
            task_hint: Description of the current task.
            limit: Max results to return.
            min_success_rate: Only return experiences with this success rate
                              or higher (0.0-1.0).

        Returns:
            List of matching experiences sorted by relevance.
        """
        query_words = task_hint.lower().split()
        scored: list[tuple[float, Experience]] = []
        now = time.time()

        for exp in self._experiences:
            # Update decay factor based on age
            days_since = (now - exp.timestamp) / 86400.0 if exp.timestamp > 0 else 0.0
            if self._forgetting_curve == "ebbinghaus":
                decay = ForgettingCurve.ebbinghaus(days_since, self._half_life)
            elif self._forgetting_curve == "linear":
                decay = ForgettingCurve.linear(days_since)
            elif self._forgetting_curve == "none":
                decay = 1.0
            else:
                decay = ForgettingCurve.ebbinghaus(days_since, self._half_life)
            exp.decay_factor = decay

            # Relevance scoring via keyword overlap
            task_lower = exp.task.lower()
            relevance = sum(1 for w in query_words if w in task_lower)
            if relevance == 0:
                continue

            # Success rate filter
            if min_success_rate > 0:
                success = 1.0 if exp.outcome == "success" else (0.5 if exp.outcome == "partial" else 0.0)
                if success < min_success_rate:
                    continue

            score = relevance * decay
            scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]

    def export(self, format: str = "json") -> list[dict]:
        """Export all experiences as a list of dicts.

        Suitable for feeding into analytics pipelines or dashboards.
        """
        return [e.model_dump() for e in self._experiences]

    @property
    def count(self) -> int:
        return len(self._experiences)

    def clear(self) -> None:
        self._experiences.clear()
