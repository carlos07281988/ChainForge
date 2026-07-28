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
"""TrainingDataCleaner — filters and deduplicates experiences for fine-tuning.

Converts raw agent experiences from CollectiveMemory into clean, deduplicated
TrainingPair lists ready for distillation or LoRA fine-tuning.
"""

from __future__ import annotations

import time
from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.collective.experience import Experience
from chainforge.logging import get_logger

logger = get_logger("enterprise.finetune.cleaner")


class TrainingPair(BaseModel):
    """A single input-to-output training pair derived from an experience."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    instruction: str = ""
    input: str = ""
    output: str = ""
    source_experience_id: str = ""
    task_type: str = "general"
    model_used: str = "unknown"
    outcome: str = "unknown"
    cost: float = 0.0
    tokens: int = 0
    timestamp: float = Field(default_factory=time.time)


class TrainingDataCleaner:
    """Filters experiences from CollectiveMemory into clean TrainingPair lists.

    Applies a pipeline of filters:
      1. **Outcome filter** — keep only successes (optionally partials).
      2. **Age filter** — drop experiences older than ``max_age_days``.
      3. **Deduplication** — remove duplicates by task similarity (Jaccard on
         tokenised task descriptions).

    Usage:
        cleaner = TrainingDataCleaner()
        pairs = cleaner.clean(
            memory.export(), min_success_rate=0.8, max_age_days=90
        )
        # → list[TrainingPair] ready for distillation
    """

    def __init__(
        self,
        min_success_rate: float = 0.8,
        max_age_days: int = 90,
        dedup_threshold: float = 0.85,
    ):
        self._min_success_rate = min_success_rate
        self._max_age_days = max_age_days
        self._dedup_threshold = dedup_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(
        self,
        experiences: list[dict] | list[Experience],
        min_success_rate: float | None = None,
        max_age_days: int | None = None,
        dedup_threshold: float | None = None,
    ) -> list[TrainingPair]:
        """Clean a batch of experiences and return training-ready pairs.

        Args:
            experiences: Raw experience dicts or Experience objects from
                CollectiveMemory (via ``memory.export()`` or direct list).
            min_success_rate: Override success-rate threshold (0.0–1.0).
            max_age_days: Override maximum age in days.
            dedup_threshold: Override Jaccard similarity threshold for
                deduplication (0.0–1.0).

        Returns:
            Deduplicated list of TrainingPair objects.
        """
        sr = min_success_rate if min_success_rate is not None else self._min_success_rate
        age = max_age_days if max_age_days is not None else self._max_age_days
        dedup = dedup_threshold if dedup_threshold is not None else self._dedup_threshold

        exps = self._normalise(experiences)
        logger.debug(f"Cleaning {len(exps)} experiences (sr={sr}, age={age}d)")

        # Step 1 — outcome filter
        kept = self._filter_outcomes(exps, sr)

        # Step 2 — age filter
        kept = self._filter_age(kept, age)

        # Step 3 — convert to TrainingPair
        pairs = [self._to_pair(exp) for exp in kept]

        # Step 4 — deduplicate
        pairs = self._deduplicate(pairs, dedup)

        logger.info(
            f"Cleaned: {len(pairs)} pairs from {len(exps)} experiences "
            f"({len(exps) - len(pairs)} filtered)"
        )
        return pairs

    # ------------------------------------------------------------------
    # Internal filter helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(experiences: list[dict] | list[Experience]) -> list[Experience]:
        """Accept either raw dicts or Experience objects."""
        out: list[Experience] = []
        for e in experiences:
            if isinstance(e, Experience):
                out.append(e)
            elif isinstance(e, dict):
                out.append(Experience(**e))
            else:
                logger.warning(f"Skipping unexpected type: {type(e)}")
        return out

    def _filter_outcomes(
        self, exps: list[Experience], min_sr: float
    ) -> list[Experience]:
        """Remove experiences whose outcome success-rate is below threshold."""
        kept: list[Experience] = []
        for exp in exps:
            success = (
                1.0 if exp.outcome == "success"
                else 0.5 if exp.outcome == "partial"
                else 0.0
            )
            if success >= min_sr:
                kept.append(exp)
            else:
                logger.debug(f"Filtered (outcome={exp.outcome}): {exp.id}")
        return kept

    def _filter_age(
        self, exps: list[Experience], max_days: int
    ) -> list[Experience]:
        """Remove experiences older than max_age_days."""
        now = time.time()
        max_seconds = max_days * 86400.0
        kept: list[Experience] = []
        for exp in exps:
            age_s = now - exp.timestamp if exp.timestamp > 0 else 0.0
            if age_s <= max_seconds:
                kept.append(exp)
            else:
                logger.debug(f"Filtered (age={age_s / 86400.0:.1f}d): {exp.id}")
        return kept

    @staticmethod
    def _to_pair(exp: Experience) -> TrainingPair:
        """Convert a single Experience to a TrainingPair."""
        return TrainingPair(
            instruction=exp.task,
            input="",
            output=exp.feedback or f"outcome={exp.outcome}",
            source_experience_id=exp.id,
            task_type=exp.task_type,
            model_used=exp.model_used,
            outcome=exp.outcome,
            cost=exp.cost,
            tokens=exp.tokens,
            timestamp=exp.timestamp,
        )

    def _deduplicate(
        self, pairs: list[TrainingPair], threshold: float
    ) -> list[TrainingPair]:
        """Remove near-duplicate pairs using Jaccard similarity on task text."""
        if not pairs:
            return []

        def _tokens(text: str) -> set[str]:
            return set(text.lower().split())

        kept: list[TrainingPair] = []
        for pair in pairs:
            is_dup = False
            tokens_a = _tokens(pair.instruction)
            if not tokens_a:
                kept.append(pair)
                continue
            for existing in kept:
                tokens_b = _tokens(existing.instruction)
                if not tokens_b:
                    continue
                intersection = tokens_a & tokens_b
                union = tokens_a | tokens_b
                jaccard = len(intersection) / len(union) if union else 0.0
                if jaccard >= threshold:
                    is_dup = True
                    logger.debug(f"Dedup: '{pair.instruction[:60]}' ~ '{existing.instruction[:60]}' (J={jaccard:.2f})")
                    break
            if not is_dup:
                kept.append(pair)
        return kept

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def task_distribution(self, pairs: list[TrainingPair]) -> dict[str, int]:
        """Return a histogram of task types in the cleaned pairs."""
        return dict(Counter(p.task_type for p in pairs))

    @property
    def min_success_rate(self) -> float:
        return self._min_success_rate

    @property
    def max_age_days(self) -> int:
        return self._max_age_days
