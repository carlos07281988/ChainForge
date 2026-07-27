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
"""GovernancePolicy + PolicyEngine — declarative governance rules.

Policies are evaluated against data labels to determine which model
providers are allowed, whether the request is blocked, and whether
model version pinning is enforced.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("governance.policy")


class GovernancePolicy(BaseModel):
    """A declarative governance rule.

    Each policy maps data sensitivity labels to model provider constraints.

    Attributes:
        name: Human-readable policy name.
        description: What this policy enforces.
        data_labels: Which data labels trigger this policy
                     (e.g. "pii", "internal", "public").
        model_provider: Required provider — "nim", "ollama", "openai", etc.
                        None means no restriction.
        region: Data residency region — "cn-east", "us-west", etc.
                None means no restriction.
        version_pin: Lock to a specific model version. None means latest.
        action: "enforce" (hard block), "audit_only" (log but allow),
                "warn" (log + annotate response).
        priority: Higher priority policies are evaluated first.
    """

    name: str = Field(description="Policy name")
    description: str = Field(default="", description="What this policy enforces")
    data_labels: list[str] = Field(default_factory=list,
                                    description="Triggering data labels")
    model_provider: str | None = Field(default=None,
                                        description="Required provider")
    region: str | None = Field(default=None,
                               description="Data residency region")
    version_pin: str | None = Field(default=None,
                                     description="Locked model version")
    action: str = Field(default="enforce",
                        description="enforce | audit_only | warn")
    priority: int = Field(default=0, description="Evaluation priority (higher = first)")

    def matches(self, labels: list[str]) -> bool:
        """Check if this policy's data_labels intersect with the given labels."""
        if not self.data_labels:
            return True
        return any(label in self.data_labels for label in labels)


class PolicyDecision(BaseModel):
    """Result of evaluating all governance policies against a set of labels.

    Attributes:
        allowed_providers: Set of provider names that are allowed.
                           Empty means all are allowed.
        blocked: Whether the request should be blocked entirely.
        block_reason: Reason for block, if blocked=True.
        version_pins: Dict of provider → version to use.
        audit_tags: Tags to attach to the audit log.
        warnings: List of warning messages for the caller.
    """

    allowed_providers: list[str] = Field(default_factory=list)
    blocked: bool = Field(default=False)
    block_reason: str = Field(default="")
    version_pins: dict[str, str] = Field(default_factory=dict)
    audit_tags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_restricted(self) -> bool:
        """True if provider choice is constrained by policy."""
        return len(self.allowed_providers) > 0


class PolicyEngine:
    """Evaluates GovernancePolicies against data labels.

    Usage:
        engine = PolicyEngine(policies=[
            GovernancePolicy(name="pii-local", data_labels=["pii"],
                             model_provider="nim", action="enforce"),
        ])
        decision = await engine.evaluate(["pii"], context={})
    """

    def __init__(self, policies: list[GovernancePolicy] | None = None):
        self._policies = sorted(
            policies or [],
            key=lambda p: p.priority,
            reverse=True,
        )

    @property
    def policies(self) -> list[GovernancePolicy]:
        return list(self._policies)

    def add_policy(self, policy: GovernancePolicy) -> None:
        """Add a policy and re-sort by priority."""
        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority, reverse=True)

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name. Returns True if found and removed."""
        count_before = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        return len(self._policies) < count_before

    async def evaluate(
        self,
        labels: list[str],
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate all matching policies against the given data labels.

        Args:
            labels: Data sensitivity labels (e.g. ["pii", "internal"]).
            context: Optional execution context (user_id, session_id, etc.).

        Returns:
            PolicyDecision with allowed providers, block status, version pins.
        """
        ctx = context or {}
        decision = PolicyDecision()

        enforce_providers_set: set[str] = set()
        audit_tags: list[str] = []

        for policy in self._policies:
            if not policy.matches(labels):
                continue

            audit_tags.append(f"policy:{policy.name}")

            if policy.action == "enforce":
                if policy.model_provider:
                    enforce_providers_set.add(policy.model_provider)
                if policy.version_pin:
                    if policy.model_provider:
                        decision.version_pins[policy.model_provider] = policy.version_pin
            elif policy.action == "warn":
                decision.warnings.append(
                    f"[{policy.name}] {policy.description or 'Policy warning'}"
                )

        if enforce_providers_set:
            decision.allowed_providers = sorted(enforce_providers_set)

        decision.audit_tags = audit_tags

        if decision.allowed_providers:
            logger.debug(
                f"Policy engine restricted providers to {decision.allowed_providers}",
                extra={"labels": labels, "audit_tags": audit_tags},
            )

        return decision
