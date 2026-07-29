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
"""Prompt Security Scanner — SAST engine for agent prompts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from chainforge.enterprise.promptsec.rules import (
    BUILTIN_RULES,
    Vulnerability,
    VulnerabilitySeverity,
)
from chainforge.logging import get_logger

logger = get_logger("enterprise.promptsec")


@dataclass
class PromptScanReport:
    """Result of a prompt security scan.

    Attributes:
        risk_score: Overall risk from 0.0 (safe) to 10.0 (critical).
        vulnerabilities: List of detected vulnerabilities.
        recommendations: Deduplicated fix recommendations.
        prompt_length: Character count of the scanned prompt.
        rules_checked: Number of rules applied.
        passed: Whether the prompt passed (risk_score < 4.0).
    """

    risk_score: float = 0.0
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    prompt_length: int = 0
    rules_checked: int = 0
    passed: bool = True

    def to_json(self, indent: int = 2) -> str:
        """Serialize the report to a JSON string."""
        return json.dumps(
            {
                "risk_score": round(self.risk_score, 2),
                "passed": self.passed,
                "prompt_length": self.prompt_length,
                "rules_checked": self.rules_checked,
                "vulnerability_count": len(self.vulnerabilities),
                "vulnerabilities": [
                    {
                        "type": v.type,
                        "severity": v.severity.name,
                        "line": v.line,
                        "description": v.description,
                        "recommendation": v.recommendation,
                    }
                    for v in self.vulnerabilities
                ],
                "recommendations": self.recommendations,
            },
            indent=indent,
        )

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        status = "PASSED" if self.passed else "FAILED"
        counts = {
            sev.name: sum(1 for v in self.vulnerabilities if v.severity == sev)
            for sev in VulnerabilitySeverity
        }
        detail = ", ".join(
            f"{sev.name}={counts[sev.name]}" for sev in VulnerabilitySeverity if counts[sev.name]
        ) or "none"
        return (
            f"[{status}] risk={self.risk_score:.1f}/10 "
            f"({detail}, {self.rules_checked} rules checked, {self.prompt_length} chars)"
        )


class PromptSecurityScanner:
    """SAST scanner for agent prompts.

    Applies a configurable set of detection rules against prompt text
    to find security issues: leaked credentials, injection surfaces,
    overly permissive language, system prompt leaks, and more.

    Usage::

        scanner = PromptSecurityScanner()
        report = scanner.scan(prompt_text)
        if not report.passed:
            print(report.to_json())
    """

    # Severity weight multipliers for risk score calculation
    _WEIGHTS = {
        VulnerabilitySeverity.CRITICAL: 4.0,
        VulnerabilitySeverity.HIGH: 2.5,
        VulnerabilitySeverity.MEDIUM: 1.5,
        VulnerabilitySeverity.LOW: 0.5,
    }

    _MAX_SCORE = 10.0

    def __init__(self, custom_rules: Sequence | None = None):
        """Initialize the scanner with an optional set of custom rules.

        Args:
            custom_rules: Optional additional rules in the same format as BUILTIN_RULES.
                          Each rule is (name, check_fn, severity, recommendation).
        """
        self._rules: list = list(BUILTIN_RULES)
        if custom_rules:
            self._rules.extend(custom_rules)

    def scan(self, prompt_text: str) -> PromptScanReport:
        """Scan a prompt string for security vulnerabilities.

        Args:
            prompt_text: The prompt text to analyze.

        Returns:
            A PromptScanReport with findings and risk score.
        """
        vulnerabilities: list[Vulnerability] = []
        recommendations_set: set[str] = set()

        for name, check_fn, severity, recommendation in self._rules:
            try:
                findings = check_fn(prompt_text)
            except Exception:
                logger.warning("Rule %s raised an exception; skipping", name)
                continue

            for line_no, description in findings:
                vulnerability = Vulnerability(
                    type=name,
                    severity=severity,
                    line=line_no,
                    description=description,
                    recommendation=recommendation,
                )
                vulnerabilities.append(vulnerability)
                recommendations_set.add(recommendation)

        # Compute weighted risk score, capped at MAX_SCORE
        raw_score = 0.0
        for v in vulnerabilities:
            raw_score += self._WEIGHTS.get(v.severity, 0.0)
        risk_score = round(min(raw_score, self._MAX_SCORE), 2)

        return PromptScanReport(
            risk_score=risk_score,
            vulnerabilities=vulnerabilities,
            recommendations=sorted(recommendations_set),
            prompt_length=len(prompt_text),
            rules_checked=len(self._rules),
            passed=risk_score < 4.0,
        )

    def scan_file(self, path: str | Path) -> PromptScanReport:
        """Scan a single file containing prompt text.

        Args:
            path: Path to a file containing the prompt text.

        Returns:
            A PromptScanReport for the file contents.
        """
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        report = self.scan(text)
        logger.info("Scanned %s: %s", path.name, report.summary())
        return report

    def scan_directory(self, path: str | Path, glob: str = "*.txt") -> list[PromptScanReport]:
        """Scan all matching files in a directory.

        Args:
            path: Directory path to scan.
            glob: File glob pattern (default: ``*.txt``).

        Returns:
            A list of PromptScanReport, one per scanned file.
        """
        path = Path(path)
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        reports: list[PromptScanReport] = []
        for file_path in sorted(path.glob(glob)):
            if file_path.is_file():
                try:
                    report = self.scan_file(file_path)
                    reports.append(report)
                except Exception:
                    logger.warning("Could not scan %s; skipping", file_path.name)

        logger.info(
            "Scanned %d files in %s: %d passed",
            len(reports),
            path.name,
            sum(1 for r in reports if r.passed),
        )
        return reports
