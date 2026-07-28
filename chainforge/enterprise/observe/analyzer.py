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
"""Root cause analysis engine — heuristic attribution of anomaly events to likely upstream causes."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("enterprise.observe")


class RootCauseReport(BaseModel):
    """Analysis report attributing an anomaly to one or more root cause hypotheses."""

    report_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    anomaly_id: str = ""
    anomaly_type: str = ""
    root_cause: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    def to_json(self) -> dict:
        return self.model_dump()


class RootCauseAnalyzer:
    """Heuristically attribute anomaly events to likely upstream root causes.

    Each anomaly type has a set of detection rules that map metric snapshots
    to one or more plausible root causes with a confidence score.

    Usage::

        analyzer = RootCauseAnalyzer()
        report = analyzer.analyze(anomaly_event)
        print(report.root_cause, report.confidence)
    """

    # Heuristic rules keyed by anomaly type → (condition predicate, root_cause, confidence)
    _RULES: dict[str, list[tuple]] = {
        "failure_rate_spike": [
            (
                lambda m: m.get("failure_rate", 0) > 0.5,
                "Downstream service returning 5xx errors — check upstream dependency health.",
                0.92,
            ),
            (
                lambda m: m.get("failure_rate", 0) > 0.3,
                "Elevated failure rate — possible API rate-limiting or quota exhaustion.",
                0.78,
            ),
            (
                lambda m: m.get("failure_rate", 0) > 0.1,
                "Mild failure rate increase — investigate recent deployment or config change.",
                0.55,
            ),
        ],
        "new_tool_detected": [
            (
                lambda m: True,
                "Agent attempted to use an unknown tool — possible hallucination or tool registry misconfiguration.",
                0.85,
            ),
        ],
        "token_spike": [
            (
                lambda m: m.get("tokens_per_call", 0) > 10000,
                "Token consumption spike — likely RAG retrieval returning oversized context chunks.",
                0.88,
            ),
            (
                lambda m: m.get("tokens_per_call", 0) > 5000,
                "Above-average token usage — check for redundant tool results or verbose system prompts.",
                0.70,
            ),
        ],
        "latency_spike": [
            (
                lambda m: m.get("avg_latency_ms", 0) > 10000,
                "Severe latency spike — external API timeout or slow upstream model inference.",
                0.90,
            ),
            (
                lambda m: m.get("avg_latency_ms", 0) > 5000,
                "Moderate latency increase — possible model overload or network congestion.",
                0.65,
            ),
        ],
        "cost_anomaly": [
            (
                lambda m: m.get("total_cost", 0) > 1.0,
                "Cost overrun — expensive model usage or excessive tool calls.",
                0.82,
            ),
        ],
    }

    def analyze(self, anomaly: dict | Any) -> RootCauseReport:
        """Analyze an anomaly and produce a root cause report.

        Accepts either a dict (snapshot from AnomalyEvent) or an AnomalyEvent instance.
        """
        # Normalize input
        if isinstance(anomaly, dict):
            anomaly_id = anomaly.get("id", "unknown")
            anomaly_type = anomaly.get("type", "unknown")
            metrics = anomaly.get("metrics_snapshot", {})
        else:
            anomaly_id = getattr(anomaly, "id", "unknown")
            anomaly_type = getattr(anomaly, "type", "unknown")
            metrics = getattr(anomaly, "metrics_snapshot", {})

        # Find matching rules for this anomaly type
        rules = self._RULES.get(anomaly_type, [])
        best_cause = "No specific root cause identified. Conduct manual investigation."
        best_confidence = 0.15
        evidence: list[str] = []

        for predicate, cause, confidence in rules:
            try:
                if predicate(metrics):
                    if confidence > best_confidence:
                        best_cause = cause
                        best_confidence = confidence
                    evidence.append(f"Matched rule: {cause[:80]}... (confidence={confidence})")
            except Exception:
                logger.debug("Root cause rule evaluation failed for type=%s", anomaly_type)

        # Fallback when no rules matched: attribute generically
        if not evidence:
            evidence.append(
                f"No specific heuristic matched for anomaly type '{anomaly_type}' "
                f"with metrics={metrics}"
            )

        return RootCauseReport(
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            root_cause=best_cause,
            confidence=best_confidence,
            evidence=evidence,
            recommendations=self._generate_recommendations(anomaly_type, best_confidence),
        )

    def _generate_recommendations(self, anomaly_type: str, confidence: float) -> list[str]:
        recs: list[str] = []
        if anomaly_type == "failure_rate_spike":
            recs.append("Check downstream API health dashboards.")
            recs.append("Review recent deployment changelog for breaking changes.")
        elif anomaly_type == "new_tool_detected":
            recs.append("Audit tool registry for missing or misspelled tool names.")
        elif anomaly_type == "token_spike":
            recs.append("Review RAG chunk sizes and prompt template lengths.")
        elif anomaly_type == "latency_spike":
            recs.append("Check upstream model provider status page.")
            recs.append("Review network latency metrics between agent and external APIs.")
        elif anomaly_type == "cost_anomaly":
            recs.append("Review model selection — consider switching to a cheaper model.")
        if confidence < 0.5:
            recs.append("Low confidence — escalate to on-call engineer for manual review.")
        return recs
