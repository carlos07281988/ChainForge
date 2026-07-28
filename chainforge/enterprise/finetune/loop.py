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
"""FineTuningLoop — orchestrates the full feedback loop from memory to LoRA weights.

Collective Memory → Clean → Validate → Train → Adapter

This is the top-level orchestrator. It pulls experiences from a
CollectiveMemory instance, cleans them, validates quality, and (if the
gates pass) triggers LoRA fine-tuning.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.collective.memory import CollectiveMemory
from chainforge.enterprise.distill.adapter import LoRAConfig
from chainforge.enterprise.finetune.cleaner import TrainingDataCleaner, TrainingPair
from chainforge.enterprise.finetune.quality import QualityGate, QualityReport
from chainforge.enterprise.finetune.trainer import LoRATrainer, TrainResult
from chainforge.logging import get_logger

logger = get_logger("enterprise.finetune.loop")


class FineTuningResult(BaseModel):
    """Complete result of a fine-tuning loop run.

    Attributes:
        model_path: Filesystem path to the trained LoRA adapter weights.
        training_pairs: Number of TrainingPair instances fed to the trainer.
        improvement_estimate: Estimated improvement in agent success rate
            (0.0–1.0 scale). Derived from data quality and volume heuristics.
        eval_score: Normalised evaluation score (0.0–1.0).
        quality_report: The QualityReport from the validation step.
        train_result: The TrainResult from the training step (None if training
            was skipped).
        status: "trained" | "gated" | "no_data" | "error".
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_path: str = ""
    training_pairs: int = 0
    improvement_estimate: float = 0.0
    eval_score: float = 0.0
    quality_report: QualityReport | None = None
    train_result: TrainResult | None = None
    status: str = "pending"


class FineTuningLoop:
    """Orchestrates the full agent fine-tuning feedback loop.

    Pipeline:
      1. Pull experiences from ``source_memory``.
      2. Clean with `TrainingDataCleaner`.
      3. Validate with `QualityGate`.
      4. If passed, call `LoRATrainer`.
      5. Return `FineTuningResult`.

    Usage:
        memory = CollectiveMemory(namespace="customer-support")
        memory.add(Experience(id="1", task="refund", outcome="success", ...))

        loop = FineTuningLoop(
            source_memory=memory,
            target_model="qwen2.5-3b",
            quality_gate=QualityGate(min_experiences=5),
        )
        result = await loop.run()
        assert result.status == "trained"
    """

    def __init__(
        self,
        source_memory: CollectiveMemory,
        target_model: str = "qwen2.5-3b",
        quality_gate: QualityGate | None = None,
        lora_config: LoRAConfig | None = None,
        framework: str = "unsloth",
        min_success_rate: float = 0.8,
        max_age_days: int = 90,
    ):
        self._source_memory = source_memory
        self._target_model = target_model
        self._quality_gate = quality_gate or QualityGate()
        self._lora_config = lora_config or LoRAConfig()
        self._framework = framework
        self._cleaner = TrainingDataCleaner(
            min_success_rate=min_success_rate,
            max_age_days=max_age_days,
        )
        self._trainer = LoRATrainer(
            adapter_config=self._lora_config,
            base_model=target_model,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        min_success_rate: float | None = None,
        max_age_days: int | None = None,
        epochs: int = 3,
    ) -> FineTuningResult:
        """Execute the full fine-tuning loop.

        Args:
            min_success_rate: Override success-rate threshold for the cleaner.
            max_age_days: Override max age threshold for the cleaner.
            epochs: Number of training epochs.

        Returns:
            FineTuningResult with the final status and diagnostics.
        """
        # Step 1 — Pull raw experiences from shared memory
        raw_dicts = self._source_memory.export()
        if not raw_dicts:
            logger.warning("FineTuningLoop: source memory is empty — nothing to train on")
            return FineTuningResult(
                status="no_data",
                improvement_estimate=0.0,
                eval_score=0.0,
            )

        logger.info(
            f"FineTuningLoop: pulled {len(raw_dicts)} raw experiences "
            f"from namespace={self._source_memory.namespace}"
        )

        # Step 2 — Clean
        pairs = self._cleaner.clean(
            raw_dicts,
            min_success_rate=min_success_rate,
            max_age_days=max_age_days,
        )

        if not pairs:
            logger.warning("FineTuningLoop: no pairs survived cleaning")
            return FineTuningResult(
                status="no_data",
                improvement_estimate=0.0,
                eval_score=0.0,
            )

        # Step 3 — Validate (convert pairs back to experiences for quality gate)
        from chainforge.enterprise.collective.experience import Experience

        exp_for_qa = [
            Experience(
                id=p.source_experience_id,
                task=p.instruction,
                task_type=p.task_type,
                model_used=p.model_used,
                outcome=p.outcome,
                cost=p.cost,
                tokens=p.tokens,
                timestamp=p.timestamp,
            )
            for p in pairs
        ]
        qa_report = self._quality_gate.validate(exp_for_qa, filtered_count=len(pairs))

        if not qa_report.passed:
            logger.warning(f"FineTuningLoop: gated — {qa_report.reason}")
            return FineTuningResult(
                quality_report=qa_report,
                status="gated",
                training_pairs=len(pairs),
                improvement_estimate=self._estimate_improvement(pairs),
                eval_score=self._compute_eval_score(pairs),
            )

        # Step 4 — Train
        train_result = self._trainer.train(
            pairs,
            adapter_config=self._lora_config,
            framework=self._framework,
            epochs=epochs,
        )

        # Step 5 — Build result
        improvement = self._estimate_improvement(pairs)
        eval_score = self._compute_eval_score(pairs)

        result = FineTuningResult(
            model_path=train_result.output_path,
            training_pairs=len(pairs),
            improvement_estimate=improvement,
            eval_score=eval_score,
            quality_report=qa_report,
            train_result=train_result,
            status="trained",
        )

        logger.info(
            f"FineTuningLoop complete: model={result.model_path}, "
            f"pairs={result.training_pairs}, improvement={improvement:.1%}, "
            f"eval={eval_score:.2f}"
        )
        return result

    # ------------------------------------------------------------------
    # Scoring heuristics
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_improvement(pairs: list[TrainingPair]) -> float:
        """Estimate improvement from data volume and quality.

        Heuristic: log-scale improvement with diminishing returns.
        """
        n = len(pairs)
        if n == 0:
            return 0.0
        successes = sum(1 for p in pairs if p.outcome == "success")
        quality = successes / n
        # Logarithmic scaling: 10 pairs → ~0.05, 100 → ~0.10, 1000 → ~0.15
        scale = min(0.25, 0.05 * (n ** 0.3))
        return round(quality * scale, 4)

    @staticmethod
    def _compute_eval_score(pairs: list[TrainingPair]) -> float:
        """Compute a normalised evaluation score from the pairs.

        Based on success rate, task diversity, and data volume.
        """
        if not pairs:
            return 0.0
        n = len(pairs)
        successes = sum(1 for p in pairs if p.outcome == "success")
        sr = successes / n

        unique_tasks = len({p.task_type for p in pairs})
        diversity = min(1.0, unique_tasks / 5.0)

        volume_factor = min(1.0, n / 200.0)

        return round((sr * 0.5 + diversity * 0.3 + volume_factor * 0.2), 4)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def source_memory(self) -> CollectiveMemory:
        return self._source_memory

    @property
    def target_model(self) -> str:
        return self._target_model

    @property
    def quality_gate(self) -> QualityGate:
        return self._quality_gate

    @property
    def lora_config(self) -> LoRAConfig:
        return self._lora_config

    @property
    def cleaner(self) -> TrainingDataCleaner:
        return self._cleaner

    @property
    def trainer(self) -> LoRATrainer:
        return self._trainer
