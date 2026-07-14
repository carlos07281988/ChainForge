# Copyright 2024 ChainForge Contributors
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
"""Base types for the guardrails system."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class GuardrailAction(str, Enum):
    """Action to take when a guardrail check fails."""
    block = "block"          # Block the request entirely
    flag = "flag"            # Flag for review, but allow
    rewrite = "rewrite"      # Rewrite the content safely
    warn = "warn"            # Log warning, continue


class GuardrailSeverity(str, Enum):
    """Severity of a guardrail violation."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GuardrailResult(BaseModel):
    """Result of a guardrail check."""
    passed: bool = Field(default=True, description="Whether the check passed")
    action: GuardrailAction = Field(default=GuardrailAction.block, description="Action taken")
    severity: GuardrailSeverity = Field(default=GuardrailSeverity.low, description="Violation severity")
    reason: str = Field(default="", description="Human-readable reason")
    category: str = Field(default="general", description="Guardrail category")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Risk score 0-1")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Guardrail(Protocol):
    """Protocol for guardrail implementations."""

    name: str = "guardrail"

    async def check(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Check *text* against this guardrail.

        Args:
            text: The text to check (prompt or response).
            context: Optional context (role, history, tool results, etc.).

        Returns:
            GuardrailResult indicating pass/fail and action.
        """
        ...


# ── Result helpers ──────────────────────────────────────────────────────────


def pass_result(category: str = "general", **kwargs) -> GuardrailResult:
    """Create a passing guardrail result."""
    return GuardrailResult(passed=True, category=category, **kwargs)


def block_result(reason: str, category: str = "general", severity: GuardrailSeverity = GuardrailSeverity.medium, **kwargs) -> GuardrailResult:
    """Create a blocking guardrail result."""
    return GuardrailResult(
        passed=False,
        action=GuardrailAction.block,
        severity=severity,
        reason=reason,
        category=category,
        risk_score={"low": 0.3, "medium": 0.5, "high": 0.8, "critical": 1.0}.get(severity.value, 0.5),
        **kwargs,
    )


def flag_result(reason: str, category: str = "general", severity: GuardrailSeverity = GuardrailSeverity.low) -> GuardrailResult:
    """Create a flagging (allow but warn) guardrail result."""
    return GuardrailResult(
        passed=False,
        action=GuardrailAction.flag,
        severity=severity,
        reason=reason,
        category=category,
        risk_score=0.3,
    )
