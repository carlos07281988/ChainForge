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
"""DataResidency — enforce data locality for sensitive data.

Maps data sensitivity labels to allowed provider categories. Used by
PolicyEngine and PolicyAwareRouter to keep PII/internal data on
local infrastructure.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("governance.residency")


class ResidencyRules(BaseModel):
    """A set of residency rules mapping data labels to allowed providers."""

    label: str = Field(description="Data sensitivity label")
    allowed_providers: list[str] = Field(
        description="Provider names allowed for this label"
    )
    description: str = Field(default="")


class DataResidency:
    """Data residency controller — determines which providers are allowed
    for a given set of data sensitivity labels.

    Built-in rules:
        pii      → nim, ollama (local only)
        internal → nim, ollama (local only)
        public   → all providers
        finance  → nim, ollama, bedrock (local + regulated cloud)

    Usage:
        residency = DataResidency()
        providers = residency.allowed_providers(["pii"])
        # → {"nim", "ollama"}

        # Add custom rule
        residency.add_rule("healthcare", ["nim"], "HIPAA data must stay local")
    """

    DEFAULT_RULES: ClassVar[dict[str, set[str]]] = {
        "pii":        {"nim", "ollama"},
        "internal":   {"nim", "ollama"},
        "finance":    {"nim", "ollama", "bedrock"},
        "healthcare": {"nim", "ollama"},
        "public":     {"openai", "anthropic", "google", "deepseek",
                       "azure", "bedrock", "ollama", "nim"},
    }

    def __init__(self):
        self._rules: dict[str, set[str]] = dict(self.DEFAULT_RULES)

    def add_rule(self, label: str, providers: list[str], description: str = "") -> None:
        """Add or override a residency rule.

        Args:
            label: Data sensitivity label (e.g. "healthcare").
            providers: Allowed provider names.
            description: Human-readable reason for the rule.
        """
        self._rules[label] = set(providers)
        logger.info(f"Added residency rule: {label} → {set(providers)}")

    def remove_rule(self, label: str) -> bool:
        """Remove a custom rule. Built-in rules cannot be removed."""
        if label in self.DEFAULT_RULES:
            logger.warning(f"Cannot remove built-in residency rule: {label}")
            return False
        return self._rules.pop(label, None) is not None

    def allowed_providers(self, labels: list[str]) -> set[str]:
        """Compute the set of providers allowed for ALL given labels.

        When multiple labels apply, the intersection of all matching
        rules is used (most restrictive wins).

        Args:
            labels: Data sensitivity labels (e.g. ["pii", "internal"]).

        Returns:
            Set of allowed provider names. Empty set = no restriction.
        """
        if not labels:
            return set()

        matched_rules = []
        for label in labels:
            if label in self._rules:
                matched_rules.append(self._rules[label])

        if not matched_rules:
            return set()

        result = matched_rules[0]
        for rule_set in matched_rules[1:]:
            result = result & rule_set

        logger.debug(
            f"Residency: labels={labels} → allowed={result}",
            extra={"labels": labels, "allowed": sorted(result)},
        )
        return result

    def is_allowed(self, provider: str, labels: list[str]) -> bool:
        """Check if a specific provider is allowed for the given labels.

        Returns True if no rules restrict this provider.
        """
        allowed = self.allowed_providers(labels)
        if not allowed:
            return True
        return provider in allowed

    def get_policies(self) -> list[ResidencyRules]:
        """Export all current rules (for display/debugging)."""
        return [
            ResidencyRules(
                label=label,
                allowed_providers=sorted(providers),
                description="built-in" if label in self.DEFAULT_RULES else "custom",
            )
            for label, providers in sorted(self._rules.items())
        ]
