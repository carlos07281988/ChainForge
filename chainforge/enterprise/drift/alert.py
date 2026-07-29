# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""DriftAlert — actionable alert produced from a drift detection report."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from chainforge.enterprise.drift.detector import DriftReport

Action = Literal["recommend_rollback", "run_benchmarks", "monitor", "none"]


@dataclass
class DriftAlert:
    """An actionable alert generated from a DriftReport.

    Attributes:
        severity: Severity label matching the report.
        message: Human-readable summary of what drifted.
        action: Recommended action.
        drift_report: The full underlying DriftReport.
        created_at: Unix timestamp when the alert was created.
    """

    severity: str
    message: str
    action: Action
    drift_report: DriftReport
    created_at: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        return {
            "severity": self.severity,
            "message": self.message,
            "action": self.action,
            "drift_report": self.drift_report.to_json(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_report(cls, report: DriftReport) -> DriftAlert:
        """Convenience factory that builds an alert from a DriftReport."""
        dim_summary = ", ".join(
            f"{d['dimension_name']} ({d['drift_score']:.2f})"
            for d in report.dimension_drifts
        )
        message = (
            f"Drift detected (score={report.overall_drift:.3f}, severity={report.severity}). "
            f"Top dimensions: {dim_summary}. "
            f"Causes: {', '.join(report.likely_causes)}."
        )
        return cls(
            severity=report.severity,
            message=message,
            action=report.recommendation,  # type: ignore[arg-type]
            drift_report=report,
        )
