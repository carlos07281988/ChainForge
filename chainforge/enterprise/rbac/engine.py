# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""RBAC evaluation engine — policy aggregation, conflict resolution, and access decisions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from chainforge.enterprise.rbac.policy import RBACPolicy, RBACRule


@dataclass
class AccessDecision:
    """The result of an RBAC evaluation.

    Attributes:
        allowed: Whether access was granted.
        matched_rules: Names of rules that matched the request.
        denied_by: Name of the rule that caused denial (if any).
        audit_id: Unique ID for this decision (traceable in audit logs).
        reason: Human-readable explanation of the decision.
        timestamp: Unix timestamp of the decision.
    """

    allowed: bool = False
    matched_rules: list[str] = field(default_factory=list)
    denied_by: str | None = None
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self, indent: int | None = None) -> str:
        """Serialize the decision to JSON for audit logging."""
        return json.dumps(
            {
                "allowed": self.allowed,
                "matched_rules": self.matched_rules,
                "denied_by": self.denied_by,
                "audit_id": self.audit_id,
                "reason": self.reason,
                "timestamp": self.timestamp,
            },
            indent=indent,
        )


class AgentRBAC:
    """Policy evaluation engine for agent-level RBAC.

    Aggregates multiple policies, resolves conflicts (deny > allow,
    higher priority wins), and tracks statistics.

    Usage:
        rbac = AgentRBAC(policies=[data_policy, ops_policy])
        decision = rbac.evaluate("delete", agent_identity, data_labels, context)
        if not decision.allowed:
            raise PermissionError(decision.reason)
    """

    def __init__(self, policies: list[RBACPolicy] | None = None):
        self._policies: list[RBACPolicy] = policies or []
        self._total_checks: int = 0
        self._allowed_count: int = 0
        self._denied_count: int = 0
        self._by_rule: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        action: str,
        agent_identity: dict[str, Any],
        data_labels: list[str],
        context: dict[str, Any],
    ) -> AccessDecision:
        """Evaluate whether an agent action is authorized.

        Args:
            action: The action being attempted (e.g. "access_data", "delete", "query").
            agent_identity: Dict with agent properties (verified, clearance, roles, etc.).
            data_labels: List of data classification labels (e.g. ["pii", "internal"]).
            context: Additional request context (human_approved, session_id, etc.).

        Returns:
            AccessDecision with allowed/denied status and audit information.
        """
        self._total_checks += 1

        # Build evaluation context from agent identity + data labels + request context
        eval_context: dict[str, Any] = {}

        # Merge agent identity
        eval_context.update(agent_identity)

        # Merge data labels as boolean flags (e.g. "pii" -> has_pii=True)
        for label in data_labels:
            eval_context[f"has_{label}"] = True

        # Merge request context (overrides anything above if keys conflict)
        eval_context.update(context)

        # Evaluate all policies and collect matching rules
        matched_rules: list[RBACRule] = []
        for policy in self._policies:
            matched, rule = policy.evaluate(action, eval_context)
            if matched and rule is not None:
                matched_rules.append(rule)

        # Resolve conflicts:
        # 1. If no rules matched -> default deny
        if not matched_rules:
            decision = self._deny(
                matched_rule_names=[],
                denied_by=None,
                reason=f"No policy matched for action '{action}'",
            )
            return decision

        # 2. Separate allow and deny matches
        deny_matches = [r for r in matched_rules if r.effect == "deny"]
        allow_matches = [r for r in matched_rules if r.effect == "allow"]

        # 3. Deny takes precedence: if any deny rule matched, deny
        if deny_matches:
            # Pick the highest-priority deny rule
            top_deny = max(deny_matches, key=lambda r: r.priority)
            decision = self._deny(
                matched_rule_names=[r.name for r in matched_rules],
                denied_by=top_deny.name,
                reason=f"Denied by rule '{top_deny.name}': {top_deny.description}",
            )
            return decision

        # 4. All matching rules are allow -> grant access
        top_allow = max(allow_matches, key=lambda r: r.priority)
        decision = self._allow(
            matched_rule_names=[r.name for r in matched_rules],
            reason=f"Allowed by rule '{top_allow.name}': {top_allow.description}",
        )
        return decision

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    def middleware(self) -> Callable:
        """Return an async middleware that intercepts tool_call events."""
        from chainforge.enterprise.rbac.middleware import rbac_middleware

        return rbac_middleware(self)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return evaluation statistics."""
        return {
            "total_checks": self._total_checks,
            "allowed": self._allowed_count,
            "denied": self._denied_count,
            "by_rule": dict(self._by_rule),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _allow(
        self,
        matched_rule_names: list[str],
        reason: str,
    ) -> AccessDecision:
        self._allowed_count += 1
        for name in matched_rule_names:
            self._by_rule[name] = self._by_rule.get(name, 0) + 1
        return AccessDecision(
            allowed=True,
            matched_rules=matched_rule_names,
            denied_by=None,
            reason=reason,
        )

    def _deny(
        self,
        matched_rule_names: list[str],
        denied_by: str | None,
        reason: str,
    ) -> AccessDecision:
        self._denied_count += 1
        for name in matched_rule_names:
            self._by_rule[name] = self._by_rule.get(name, 0) + 1
        return AccessDecision(
            allowed=False,
            matched_rules=matched_rule_names,
            denied_by=denied_by,
            reason=reason,
        )
