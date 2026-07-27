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
"""AuditReporter — compliance audit reports from provenance + tracing data.

Consumes ProvenanceTracker and Tracer data to generate human-readable
audit reports. Supports compliance checking against GovernancePolicies.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("governance.audit")


class ComplianceItem(BaseModel):
    """A single compliance check result.

    Attributes:
        policy_name: Which policy was checked.
        passed: Whether the check passed.
        details: Human-readable details about the check.
        evidence: Supporting evidence (event IDs, timestamps).
    """

    policy_name: str = Field(description="Policy name")
    passed: bool = Field(default=True)
    details: str = Field(default="")
    evidence: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    """A complete audit report.

    Attributes:
        report_id: Unique report identifier.
        generated_at: Unix timestamp of generation.
        time_range: (start, end) time range of audited events.
        total_events: Number of events audited.
        compliance_items: Compliance check results.
        model_calls: Number of model calls in the period.
        providers_used: Which providers were used.
        data_labels_seen: Data labels that were classified.
        raw_summary: JSON-serializable summary for machine consumption.
    """

    report_id: str = Field(default_factory=lambda: f"audit-{int(time.time())}")
    generated_at: float = Field(default_factory=time.time)
    time_range: tuple[float, float] = Field(default=(0.0, 0.0))
    total_events: int = Field(default=0)
    compliance_items: list[ComplianceItem] = Field(default_factory=list)
    model_calls: int = Field(default=0)
    providers_used: list[str] = Field(default_factory=list)
    data_labels_seen: list[str] = Field(default_factory=list)
    raw_summary: dict[str, Any] = Field(default_factory=dict)

    @property
    def compliance_score(self) -> float:
        """Fraction of compliance checks that passed. 1.0 = fully compliant."""
        if not self.compliance_items:
            return 1.0
        passed = sum(1 for c in self.compliance_items if c.passed)
        return passed / len(self.compliance_items)

    def summary(self) -> str:
        """Human-readable summary of the audit report."""
        lines = [
            f"Audit Report: {self.report_id}",
            f"Generated:   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.generated_at))}",
            f"Time Range:  {self._fmt_time(self.time_range[0])} → {self._fmt_time(self.time_range[1])}",
            f"Events:      {self.total_events}",
            f"Model Calls: {self.model_calls}",
            f"Providers:   {', '.join(self.providers_used) if self.providers_used else 'none'}",
            f"Data Labels: {', '.join(self.data_labels_seen) if self.data_labels_seen else 'none'}",
            f"Compliance:  {self.compliance_score:.0%} ({sum(1 for c in self.compliance_items if c.passed)}/{len(self.compliance_items)} passed)",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt_time(ts: float) -> str:
        if ts == 0.0:
            return "N/A"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


class AuditReporter:
    """Generates compliance audit reports from provenance and tracing data.

    Can optionally consume ProvenanceTracker and Tracer for detailed
    event-level auditing. Works standalone for lightweight usage.

    Usage:
        reporter = AuditReporter()
        reporter.record_event("model_call", {"provider": "nim", "model": "..."})
        reporter.record_event("data_label", {"labels": ["pii"]})

        report = reporter.generate_report()
        print(report.summary())
    """

    def __init__(
        self,
        provenance: Any | None = None,
        tracer: Any | None = None,
    ):
        """Initialize the audit reporter.

        Args:
            provenance: Optional ProvenanceTracker for detailed event tracing.
            tracer: Optional Tracer for span-level observability.
        """
        self._provenance = provenance
        self._tracer = tracer
        self._events: list[dict[str, Any]] = []

    def record_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Record an audit event.

        Args:
            event_type: Category — "model_call", "data_label", "policy_check",
                        "guardrail_block", "version_check".
            data: Event-specific payload.
        """
        self._events.append({
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        })
        logger.debug(f"Audit event: {event_type}", extra={"data": data})

    def generate_report(
        self,
        time_range: tuple[float, float] | None = None,
        policies: list[Any] | None = None,
    ) -> AuditReport:
        """Generate an audit report for the recorded events.

        Args:
            time_range: Optional (start, end) filter. Defaults to all events.
            policies: Optional list of GovernancePolicy to check against.

        Returns:
            AuditReport with compliance score and summary.
        """
        events = self._events
        if time_range:
            start, end = time_range
            events = [e for e in events if start <= e["timestamp"] <= end]

        model_calls = [e for e in events if e["type"] == "model_call"]
        providers_used = list(set(
            e["data"].get("provider", "unknown") for e in model_calls
        ))
        data_labels_seen = []
        for e in events:
            if e["type"] == "data_label":
                data_labels_seen.extend(e["data"].get("labels", []))

        compliance_items: list[ComplianceItem] = []

        # Check: PII data should not use cloud providers
        pii_events = [e for e in events if e["type"] == "data_label"
                      and "pii" in e["data"].get("labels", [])]
        cloud_providers_used_for_pii = []
        for e in model_calls:
            for pe in pii_events:
                if e["data"].get("provider") in ("openai", "anthropic", "google"):
                    cloud_providers_used_for_pii.append(e)

        compliance_items.append(ComplianceItem(
            policy_name="pii-local-only",
            passed=len(cloud_providers_used_for_pii) == 0,
            details=(
                f"{len(cloud_providers_used_for_pii)} PII model calls used cloud providers"
                if cloud_providers_used_for_pii
                else "All PII model calls used local providers"
            ),
            evidence=[e["data"].get("model", "") for e in cloud_providers_used_for_pii],
        ))

        # Check: Version pins honored
        version_events = [e for e in events if e["type"] == "version_check"]
        version_failures = [e for e in version_events
                           if not e["data"].get("passed", True)]
        compliance_items.append(ComplianceItem(
            policy_name="version-pin-enforcement",
            passed=len(version_failures) == 0,
            details=(
                f"{len(version_failures)} version pin violations"
                if version_failures
                else "All version pins honored"
            ),
            evidence=[json.dumps(e["data"]) for e in version_failures],
        ))

        # Custom policy checks
        if policies:
            from chainforge.governance.policy import GovernancePolicy
            for p in policies:
                if not isinstance(p, GovernancePolicy):
                    continue
                if p.action == "enforce" and p.model_provider:
                    violations = [
                        e for e in model_calls
                        if e["data"].get("provider") != p.model_provider
                        and any(label in data_labels_seen for label in p.data_labels)
                    ]
                    compliance_items.append(ComplianceItem(
                        policy_name=p.name,
                        passed=len(violations) == 0,
                        details=(
                            f"{len(violations)} calls bypassed required provider "
                            f"{p.model_provider}"
                            if violations
                            else f"All calls used {p.model_provider} as required"
                        ),
                    ))

        report = AuditReport(
            time_range=time_range or (0.0, time.time()),
            total_events=len(events),
            compliance_items=compliance_items,
            model_calls=len(model_calls),
            providers_used=providers_used,
            data_labels_seen=list(set(data_labels_seen)),
            raw_summary={
                "event_types": {
                    t: len([e for e in events if e["type"] == t])
                    for t in set(e["type"] for e in events)
                },
            },
        )

        logger.info(
            f"Audit report generated: compliance={report.compliance_score:.0%}",
            extra={"report_id": report.report_id},
        )
        return report

    def clear_events(self) -> None:
        """Clear all recorded events."""
        self._events.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)
