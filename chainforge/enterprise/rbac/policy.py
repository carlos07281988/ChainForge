# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""RBAC policy models — rule definitions, condition matching, and policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RBACRule:
    """A single RBAC rule with conditions, effect, and priority.

    Attributes:
        name: Unique rule identifier (e.g. "pii-deny", "query-allow").
        description: Human-readable explanation of the rule's purpose.
        action: Action being authorized (e.g. "access_data", "delete", "query").
        conditions: Dictionary of condition key -> expected value. All conditions
                    must match for the rule to fire.
        effect: "allow" or "deny".
        priority: Higher priority wins when multiple rules match with the same effect.
    """

    name: str
    description: str = ""
    action: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)
    effect: str = "allow"
    priority: int = 0

    def matches(self, action: str, context: dict[str, Any]) -> bool:
        """Check whether this rule matches the given action and context.

        Returns True when:
        - The action matches (or rule.action is empty, matching any action).
        - ALL conditions in self.conditions are satisfied by the context dict.
          A condition value of True means "the key must be truthy in context";
          a specific value means exact match.
        """
        # Action matching: empty action matches everything
        if self.action and self.action != action:
            return False

        # All conditions must be satisfied
        for key, expected in self.conditions.items():
            actual = context.get(key)
            if expected is True:
                # Truthiness check — the key must exist and be truthy
                if not actual:
                    return False
            elif actual != expected:
                return False

        return True


@dataclass
class RBACPolicy:
    """A named collection of RBAC rules evaluated in priority order.

    Evaluation strategy:
    - Rules are sorted by priority (descending), then by effect (deny first).
    - Returns the first matching rule.
    - Deny always takes precedence over allow when both match at the same
      priority level.
    """

    name: str
    rules: list[RBACRule] = field(default_factory=list)

    def evaluate(self, action: str, context: dict[str, Any]) -> tuple[bool, RBACRule | None]:
        """Evaluate the policy against an action and context.

        Returns:
            Tuple of (matched: bool, matched_rule: RBACRule | None).
            If no rule matches, returns (False, None) — default-deny.
        """
        # Sort: higher priority first; within same priority, deny before allow
        sorted_rules = sorted(
            self.rules,
            key=lambda r: (-r.priority, 0 if r.effect == "deny" else 1),
        )

        for rule in sorted_rules:
            if rule.matches(action, context):
                return True, rule

        return False, None

    @classmethod
    def create_default(cls) -> RBACPolicy:
        """Create a sensible default policy with built-in data governance rules.

        Built-in rules:
        - Deny PII access unless clearance >= 3
        - Deny delete without human_approval
        - Allow query for verified agents
        """
        rules = [
            RBACRule(
                name="pii-deny",
                description="Deny access to PII data unless clearance level >= 3",
                action="access_data",
                conditions={"has_pii": True},
                effect="deny",
                priority=10,
            ),
            RBACRule(
                name="pii-clearance-allow",
                description="Allow PII access with sufficient clearance",
                action="access_data",
                conditions={"has_pii": True},
                effect="allow",
                priority=10,
            ),
            RBACRule(
                name="delete-deny",
                description="Deny deletion unless human approval is granted",
                action="delete",
                conditions={"human_approved": False},
                effect="deny",
                priority=15,
            ),
            RBACRule(
                name="delete-allow",
                description="Allow deletion with human approval",
                action="delete",
                conditions={"human_approved": True},
                effect="allow",
                priority=15,
            ),
            RBACRule(
                name="query-allow-verified",
                description="Allow queries from verified agents",
                action="query",
                conditions={"verified": True},
                effect="allow",
                priority=5,
            ),
        ]
        return cls(name="default", rules=rules)
