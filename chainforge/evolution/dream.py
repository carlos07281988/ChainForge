"""Dream / Simulation Mode — predict tool outcomes before executing.

Agents simulate tool call results before actually executing them,
compare predictions with actual results, and learn from discrepancies.

Usage:
    from chainforge.evolution.dream import DreamConfig, DreamMode

    dream = DreamConfig(mode=DreamMode.light)
    dream.record_prediction("search", {"q": "weather"}, "Sunny")
    dream.record_actual("search", {"q": "weather"}, "Rainy")
    accuracy = dream.accuracy()

Levels:
  - off: no prediction
  - light: predict tool result only, one LLM call per tool
  - medium: predict + evaluate correctness, two LLM calls
  - deep: full reasoning trace simulation, three+ LLM calls
"""

from __future__ import annotations

import math
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DreamMode(str, Enum):
    """Level of dream/simulation detail."""
    off = "off"
    light = "light"
    medium = "medium"
    deep = "deep"


class DreamPrediction(BaseModel):
    """A single prediction record for post-execution comparison."""

    tool_name: str = Field(description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict)
    predicted_result: str = Field(default="")
    actual_result: str = Field(default="")
    was_accurate: bool | None = Field(default=None)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    elapsed: float = Field(default=0.0)
    timestamp: float = Field(default_factory=time.time)


class DreamConfig(BaseModel):
    """Configuration for dream/simulation mode."""

    mode: DreamMode = Field(default=DreamMode.off)
    predictions: list[DreamPrediction] = Field(default_factory=list)
    accuracy_threshold: float = Field(default=0.3, description="Accuracy below this triggers learning")

    def record_prediction(self, tool_name: str, args: dict, prediction: str, confidence: float = 0.5) -> None:
        """Record a prediction before tool execution."""
        self.predictions.append(DreamPrediction(
            tool_name=tool_name,
            arguments=args,
            predicted_result=prediction,
            confidence=confidence,
        ))

    def record_actual(self, tool_name: str, args: dict, actual: str) -> DreamPrediction | None:
        """Record actual result and compare with prediction. Returns the matched prediction or None."""
        for pred in reversed(self.predictions):
            if pred.tool_name == tool_name and pred.was_accurate is None:
                pred.actual_result = actual
                pred.was_accurate = self._compare(pred.predicted_result, actual)
                return pred
        return None

    def accuracy(self) -> float:
        """Calculate prediction accuracy across all predictions."""
        completed = [p for p in self.predictions if p.was_accurate is not None]
        if not completed:
            return 0.0
        return sum(1 for p in completed if p.was_accurate) / len(completed)

    def recent_accuracy(self, n: int = 10) -> float:
        """Calculate accuracy of the N most recent predictions."""
        completed = [p for p in self.predictions if p.was_accurate is not None][-n:]
        if not completed:
            return 0.0
        return sum(1 for p in completed if p.was_accurate) / len(completed)

    def low_confidence_patterns(self) -> list[str]:
        """Identify tools or patterns where predictions are consistently wrong."""
        tool_errors: dict[str, list[bool]] = {}
        for p in self.predictions:
            if p.was_accurate is not None:
                tool_errors.setdefault(p.tool_name, []).append(p.was_accurate)

        patterns = []
        for tool, results in tool_errors.items():
            if len(results) >= 3 and sum(results) / len(results) < self.accuracy_threshold:
                patterns.append(f"Low accuracy on {tool}: {sum(results)}/{len(results)} correct")
        return patterns

    def summary(self) -> dict:
        """Return a summary of dream mode statistics."""
        total = len(self.predictions)
        completed = [p for p in self.predictions if p.was_accurate is not None]
        return {
            "mode": self.mode.value,
            "total_predictions": total,
            "completed": len(completed),
            "accuracy": self.accuracy(),
            "patterns": self.low_confidence_patterns(),
        }

    @staticmethod
    def _compare(predicted: str, actual: str) -> bool:
        """Compare predicted vs actual result with fuzzy matching."""
        p_lower = predicted.lower().strip()
        a_lower = actual.lower().strip()
        # Exact match
        if p_lower == a_lower:
            return True
        # Contains match
        if len(p_lower) > 10 and p_lower in a_lower:
            return True
        if len(a_lower) > 10 and a_lower in p_lower:
            return True
        # Keyword overlap
        p_words = set(p_lower.split()[:5])
        a_words = set(a_lower.split()[:5])
        if len(p_words & a_words) >= min(len(p_words), len(a_words)) * 0.5:
            return True
        return False


__all__ = ["DreamConfig", "DreamMode", "DreamPrediction"]
