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
"""Root cause analysis for detected anomalies."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.logging import get_logger

logger = get_logger("enterprise.observe")


class RootCauseReport(BaseModel):
    """Result of root cause analysis for an anomaly."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    anomaly_id: str = ""
    anomaly_type: str = ""
    severity: str = "medium"
    root_cause: str = ""
    impacted_agents: list[str] = Field(default_factory=list)
    suggested_action: str = ""
    evidence: list[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
    confidence: float = 0.8

    def to_json(self) -> dict:
        return self.model_dump()


class RootCauseAnalyzer:
    """Analyze anomalies and suggest root causes.

    Usage::

        analyzer = RootCauseAnalyzer()
        report = analyzer.analyze(anomaly_event)
    """

    def __init__(self):
        self._reports: list[RootCauseReport] = []

    def analyze(self, anomaly: dict[str, Any]) -> RootCauseReport:
        """Analyze an anomaly event and produce a root cause report."""
        atype = anomaly.get("type", "unknown")
        metrics = anomaly.get("metrics_snapshot", {})

        if "failure_rate" in atype.lower() or (
            metrics.get("failure_rate", 0) > 0.1
        ):
            cause = "Provider API returning errors — check API status"
            action = (
                "Switch to fallback provider "
                "(SmartRouter 3.0 auto-recovery)"
            )
            confidence = 0.85
        elif "new_tool" in atype.lower():
            cause = "Agent introduced a previously unseen tool call"
            action = (
                "Verify tool whitelist — if legitimate, add to known tools; "
                "if suspicious, block"
            )
            confidence = 0.75
        elif "token" in atype.lower():
            cause = (
                "Agent response length increased significantly — "
                "possible prompt change or model behavior drift"
            )
            action = (
                "Check recent prompt changes; "
                "consider setting max_tokens limit"
            )
            confidence = 0.70
        else:
            cause = "Unknown anomaly pattern — recommend manual review"
            action = "Escalate to human operator"
            confidence = 0.50

        report = RootCauseReport(
            anomaly_id=anomaly.get("id", ""),
            anomaly_type=atype,
            severity=anomaly.get("severity", "medium"),
            root_cause=cause,
            suggested_action=action,
            confidence=confidence,
        )
        self._reports.append(report)
        logger.info(
            "Root cause analyzed: type=%s confidence=%.2f", atype, confidence
        )
        return report

    @property
    def reports(self) -> list[RootCauseReport]:
        return list(self._reports)
