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
"""RiskClassifier — classify agent risk tier for EU AI Act compliance."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """EU AI Act risk tiers."""
    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class RiskRule(BaseModel):
    """A single rule for risk classification.

    Attributes:
        tool_contains: Match if any agent tool name contains this string.
        data_labels: Match if any of these data labels are present.
        provider_cloud: If True, triggers when data_labels match AND
                        provider is cloud-based (not nim/ollama).
        domain: Match if the agent domain contains this string.
        risk: The risk tier to assign when this rule triggers.
        reason: Human-readable explanation.
    """

    tool_contains: str | None = Field(default=None)
    data_labels: list[str] | None = Field(default=None)
    provider_cloud: bool | None = Field(default=None)
    domain: str | None = Field(default=None)
    risk: RiskTier = Field(default=RiskTier.MINIMAL)
    reason: str = Field(default="")


_BUILTIN_RULES: list[RiskRule] = [
    RiskRule(
        tool_contains="delete", risk=RiskTier.HIGH,
        reason="Tool can delete data permanently",
    ),
    RiskRule(
        tool_contains="write_file", risk=RiskTier.HIGH,
        reason="Tool can write to filesystem",
    ),
    RiskRule(
        tool_contains="send_email", risk=RiskTier.LIMITED,
        reason="Tool can send external communications",
    ),
    RiskRule(
        data_labels=["pii"], provider_cloud=True, risk=RiskTier.HIGH,
        reason="PII data sent to cloud provider",
    ),
    RiskRule(
        domain="healthcare", risk=RiskTier.HIGH,
        reason="Healthcare decisions affect human wellbeing",
    ),
    RiskRule(
        domain="legal", risk=RiskTier.LIMITED,
        reason="Legal advice requires human oversight",
    ),
    RiskRule(
        domain="finance", risk=RiskTier.LIMITED,
        reason="Financial decisions require human oversight",
    ),
]

_TIER_ORDER = {
    RiskTier.UNACCEPTABLE: 4,
    RiskTier.HIGH: 3,
    RiskTier.LIMITED: 2,
    RiskTier.MINIMAL: 1,
}


class RiskClassifier:
    """Classify an agent's risk tier based on its tools, data labels, and domain.

    Usage:
        classifier = RiskClassifier()
        tier, rules = classifier.classify(
            tools=["delete_file", "query_db"],
            data_labels=["pii"],
            domain="healthcare",
        )
        # → (RiskTier.HIGH, [RiskRule(...), RiskRule(...)])
    """

    def __init__(self, rules: list[RiskRule] | None = None):
        self._rules: list[RiskRule] = list(_BUILTIN_RULES)
        if rules:
            self._rules.extend(rules)

    @property
    def rules(self) -> list[RiskRule]:
        """All active rules (built-in + custom)."""
        return list(self._rules)

    def classify(
        self,
        tools: list[str],
        data_labels: list[str] | None = None,
        domain: str | None = None,
    ) -> tuple[RiskTier, list[RiskRule]]:
        """Classify risk tier and return triggering rules.

        Args:
            tools: List of tool names used by the agent.
            data_labels: Optional data sensitivity labels (pii, internal, etc.).
            domain: Optional domain (healthcare, legal, finance, etc.).

        Returns:
            Tuple of (highest_risk_tier, list_of_triggering_rules).
        """
        labels = data_labels or []
        matched: list[RiskRule] = []
        highest = RiskTier.MINIMAL

        for rule in self._rules:
            triggered = False

            if rule.tool_contains and any(
                rule.tool_contains in t for t in tools
            ):
                triggered = True
            elif (
                rule.data_labels
                and rule.provider_cloud is True
                and any(l in labels for l in rule.data_labels)
            ):
                triggered = True
            elif rule.domain and domain and rule.domain in domain.lower():
                triggered = True

            if triggered:
                matched.append(rule)
                if _TIER_ORDER[rule.risk] > _TIER_ORDER[highest]:
                    highest = rule.risk

        return highest, matched
