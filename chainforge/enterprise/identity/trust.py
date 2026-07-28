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
"""TrustPolicy — rule-based trust decisions driven by reputations scores."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from chainforge.enterprise.identity.reputation import ReputationScore


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

class TrustRule(BaseModel):
    """A single rule evaluated against a ``ReputationScore``.

    *min_reputation* / *max_reputation* form an inclusive range.  When
    both are ``None`` the rule matches every score (used as a catch-all).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    min_reputation: float | None = None
    max_reputation: float | None = None
    action: str = "allow"  # "allow" | "block_all_tools" | "restrict"
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    reason: str = ""

    def matches(self, score: ReputationScore) -> bool:
        if self.min_reputation is None and self.max_reputation is None:
            return True
        if self.min_reputation is not None and score.overall < self.min_reputation:
            return False
        if self.max_reputation is not None and score.overall > self.max_reputation:
            return False
        return True


class TrustDecision(BaseModel):
    """The outcome of a trust-policy evaluation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    allowed: bool = True
    action: str = "allow"
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class TrustPolicy(BaseModel):
    """An ordered set of trust rules evaluated against reputation scores.

    Rules are checked in order; the **first** matching rule wins (most
    restrictive semantics should be achieved by ordering rules
    appropriately).

    ``TrustPolicy`` is callable, so it can be used as middleware::

        policy = TrustPolicy(rules=[...])
        decision = policy(reputation_score)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    rules: list[TrustRule] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, score: ReputationScore) -> TrustDecision:
        """Evaluate *score* against all rules, returning the first match.

        If no rule matches, a default **allow** decision is returned.
        """
        for rule in self.rules:
            if rule.matches(score):
                return TrustDecision(
                    allowed=rule.action != "block_all_tools",
                    action=rule.action,
                    allowed_tools=list(rule.allowed_tools),
                    blocked_tools=list(rule.blocked_tools),
                    reason=rule.reason,
                )
        # Default: allow everything.
        return TrustDecision(
            allowed=True,
            action="allow",
            reason="No applicable rule — default allow.",
        )

    # ------------------------------------------------------------------
    # Middleware protocol
    # ------------------------------------------------------------------

    def __call__(self, score: ReputationScore) -> TrustDecision:
        """Callable interface for middleware-compatible usage."""
        return self.evaluate(score)
