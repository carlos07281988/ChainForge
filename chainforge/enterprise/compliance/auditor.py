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
"""ComplianceAuditor — generates EU AI Act compliance audit reports."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ComplianceCheck(BaseModel):
    """A single compliance check result."""

    article: int = Field(description="EU AI Act article number")
    requirement: str = Field(description="Article requirement name")
    status: str = Field(
        default="compliant",
        description="compliant | non_compliant | not_applicable",
    )
    detail: str = Field(default="", description="Human-readable detail")


class ComplianceReport(BaseModel):
    """A complete compliance audit report."""

    report_id: str = Field(
        default_factory=lambda: f"compliance-{int(time.time())}"
    )
    generated_at: float = Field(default_factory=time.time)
    risk_tier: str = Field(default="minimal")
    checks: list[ComplianceCheck] = Field(default_factory=list)
    total_events: int = Field(default=0)
    recommendations: list[str] = Field(default_factory=list)

    @property
    def compliance_score(self) -> float:
        """Fraction of checks that passed. 1.0 = fully compliant."""
        if not self.checks:
            return 1.0
        passed = sum(1 for c in self.checks if c.status == "compliant")
        return passed / len(self.checks)

    def to_json(self) -> dict[str, Any]:
        """Export report as a JSON-serializable dict."""
        return self.model_dump()

    def to_markdown(self) -> str:
        """Export report as a Markdown string (for compliance officers)."""
        lines = [
            f"# Compliance Report: {self.report_id}",
            f"**Risk Tier:** {self.risk_tier}",
            f"**Compliance Score:** {self.compliance_score:.0%}",
            f"**Total Events:** {self.total_events}",
            "",
            "## Article Checks",
            "",
        ]
        for c in self.checks:
            icon = "✅" if c.status == "compliant" else ("❌" if c.status == "non_compliant" else "➖")
            lines.append(f"- {icon} **Art. {c.article}** ({c.requirement}): {c.detail}")
        if self.recommendations:
            lines.append("")
            lines.append("## Recommendations")
            for r in self.recommendations:
                lines.append(f"- {r}")
        return "\n".join(lines)


# ── EU AI Act article checklist ──────────────────────────────────────────

_EU_AI_ACT_ARTICLES: list[tuple[int, str, str]] = [
    (11, "Technical documentation",
     "Agent must have documented purpose, design, and limitations"),
    (12, "Record-keeping",
     "All agent actions must be logged for audit"),
    (13, "Transparency",
     "Users must be informed they are interacting with an AI agent"),
    (14, "Human oversight",
     "High-risk agents must have human-in-the-loop capability"),
    (15, "Accuracy and robustness",
     "Agent must handle errors gracefully and not produce harmful outputs"),
]


class ComplianceAuditor:
    """Records compliance events and generates audit reports.

    Usage:
        auditor = ComplianceAuditor(log_path="compliance.db")
        auditor.record("risk_classification", {"risk_tier": "high"})
        report = auditor.generate(risk_tier="high", has_hitl=True)
        print(report.to_markdown())
    """

    def __init__(
        self,
        log_path: str = "compliance.db",
        regulation: str = "eu-ai-act-2026",
    ):
        self._log_path = Path(log_path)
        self._regulation = regulation
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(str(self._log_path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "timestamp REAL, "
            "event_type TEXT, "
            "data TEXT"
            ")"
        )
        self._conn.commit()

    def record(self, event_type: str, data: dict[str, Any]) -> None:
        """Record a compliance event.

        Args:
            event_type: Category — risk_classification, hitl_required,
                        hitl_approved, guardrail_block, version_check.
            data: Event-specific payload.
        """
        if self._conn:
            self._conn.execute(
                "INSERT INTO events (timestamp, event_type, data) VALUES (?, ?, ?)",
                (time.time(), event_type, json.dumps(data)),
            )
            self._conn.commit()

    def generate(
        self,
        risk_tier: str = "minimal",
        has_hitl: bool = False,
    ) -> ComplianceReport:
        """Generate a compliance audit report.

        Args:
            risk_tier: The agent's risk tier.
            has_hitl: Whether HITL is configured for high-risk agents.

        Returns:
            ComplianceReport with article-by-article checks.
        """
        count = 0
        if self._conn:
            cur = self._conn.execute("SELECT COUNT(*) FROM events")
            count = cur.fetchone()[0]

        checks: list[ComplianceCheck] = []
        for art_num, name, detail in _EU_AI_ACT_ARTICLES:
            status: str = "compliant"
            detail_msg: str = detail

            if art_num == 12 and count == 0:
                status = "non_compliant"
                detail_msg = "No audit events recorded — record-keeping is required"
            elif art_num == 14 and not has_hitl:
                status = "non_compliant"
                detail_msg = "HITL not configured for high-risk agent"

            checks.append(ComplianceCheck(
                article=art_num,
                requirement=name,
                status=status,
                detail=detail_msg,
            ))

        recommendations = [
            c.detail for c in checks if c.status == "non_compliant"
        ]

        return ComplianceReport(
            risk_tier=risk_tier,
            checks=checks,
            total_events=count,
            recommendations=recommendations,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self) -> None:
        """Close the audit database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
