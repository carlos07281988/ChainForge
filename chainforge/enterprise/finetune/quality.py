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
"""QualityGate — validates training data quality before fine-tuning.

Ensures that only high-quality, representative datasets make it through to
LoRA training, preventing model degradation from bad data.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.collective.experience import Experience
from chainforge.logging import get_logger

logger = get_logger("enterprise.finetune.quality")


class QualityReport(BaseModel):
    """Report produced by QualityGate.validate().

    Attributes:
        passed: Whether the data passes all quality checks.
        reason: Human-readable explanation when ``passed`` is False.
        total_count: Number of experiences submitted for validation.
        filtered_count: Number of experiences that would survive filtering
            (pre-computed by the caller — this is informational).
        avg_cost: Average USD cost per experience in the filtered set.
        avg_tokens: Average token count per experience in the filtered set.
        task_type_distribution: Histogram of task types in the filtered set.
        success_rate: Fraction of submitted experiences with outcome == success.
        min_experiences_met: Whether the minimum-experience threshold was met.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    passed: bool = False
    reason: str = ""
    total_count: int = 0
    filtered_count: int = 0
    avg_cost: float = 0.0
    avg_tokens: float = 0.0
    task_type_distribution: dict[str, int] = Field(default_factory=dict)
    success_rate: float = 0.0
    min_experiences_met: bool = False


class QualityGate:
    """Validates training data quality before fine-tuning kicks off.

    Checks:
      1. **Minimum experiences** — need at least ``min_experiences`` after
         filtering to justify a fine-tuning run.
      2. **Success rate floor** — overall success rate must meet the threshold.
      3. **Task diversity** — data must span at least ``min_task_types``
         distinct task types.

    Usage:
        gate = QualityGate(min_experiences=20, min_success_rate=0.75)
        report = gate.validate(experiences, filtered_count=18)
        if report.passed:
            trainer.train(dataset)
    """

    def __init__(
        self,
        min_experiences: int = 20,
        min_success_rate: float = 0.75,
        min_task_types: int = 2,
        max_age_days: int = 90,
    ):
        self._min_experiences = min_experiences
        self._min_success_rate = min_success_rate
        self._min_task_types = min_task_types
        self._max_age_days = max_age_days

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        experiences: list[Experience],
        filtered_count: int | None = None,
    ) -> QualityReport:
        """Validate a batch of experiences for fine-tuning eligibility.

        Args:
            experiences: The (possibly pre-filtered) experiences to validate.
            filtered_count: If the caller already applied filtering (e.g. via
                TrainingDataCleaner), pass the count before filtering here so
                the report can show the difference. Otherwise defaults to
                ``len(experiences)``.

        Returns:
            QualityReport with pass/fail verdict and diagnostics.
        """
        total = len(experiences)
        fc = filtered_count if filtered_count is not None else total
        dropped = total - fc if filtered_count is not None else 0

        logger.debug(f"QualityGate: validating {total} experiences (filtered={fc})")

        # Compute aggregate metrics
        costs = [e.cost for e in experiences if e.cost > 0]
        tokens_list = [e.tokens for e in experiences if e.tokens > 0]
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        avg_tokens = sum(tokens_list) / len(tokens_list) if tokens_list else 0.0

        task_types = Counter(e.task_type for e in experiences)
        successes = sum(1 for e in experiences if e.outcome == "success")
        sr = successes / total if total > 0 else 0.0

        # Gates
        checks: list[tuple[bool, str]] = []

        # Gate 1 — minimum experiences
        min_met = fc >= self._min_experiences
        checks.append((
            min_met,
            f"Not enough experiences: {fc} < {self._min_experiences}" if not min_met else "",
        ))

        # Gate 2 — success rate
        sr_met = sr >= self._min_success_rate
        checks.append((
            sr_met,
            f"Success rate too low: {sr:.1%} < {self._min_success_rate:.0%}" if not sr_met else "",
        ))

        # Gate 3 — task diversity
        div_met = len(task_types) >= self._min_task_types
        checks.append((
            div_met,
            f"Task type diversity too low: {len(task_types)} < {self._min_task_types}" if not div_met else "",
        ))

        all_passed = all(p for p, _ in checks)
        reasons = [r for _, r in checks if r]

        report = QualityReport(
            passed=all_passed,
            reason="; ".join(reasons) if reasons else "All quality gates passed",
            total_count=total,
            filtered_count=fc,
            avg_cost=round(avg_cost, 6),
            avg_tokens=round(avg_tokens, 1),
            task_type_distribution=dict(task_types),
            success_rate=round(sr, 4),
            min_experiences_met=min_met,
        )

        if all_passed:
            logger.info(f"QualityGate PASSED: {fc} experiences, {len(task_types)} types, sr={sr:.1%}")
        else:
            logger.warning(f"QualityGate FAILED: {report.reason}")

        return report

    def should_train(self, report: QualityReport) -> bool:
        """Convenience: returns True if the report says training should proceed."""
        return report.passed

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def min_experiences(self) -> int:
        return self._min_experiences

    @property
    def min_success_rate(self) -> float:
        return self._min_success_rate

    @property
    def min_task_types(self) -> int:
        return self._min_task_types

    @property
    def max_age_days(self) -> int:
        return self._max_age_days
