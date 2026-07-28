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
"""ComplianceGuard — middleware that enforces EU AI Act compliance."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.enterprise.compliance.classifier import RiskClassifier, RiskTier
from chainforge.enterprise.compliance.hitl import HITLPolicy, ApprovalRequest
from chainforge.enterprise.compliance.auditor import ComplianceAuditor
from chainforge.logging import get_logger

logger = get_logger("enterprise.compliance")


class ComplianceGuard:
    """Middleware: classify risk, enforce HITL, record audit events.

    Usage:
        classifier = RiskClassifier()
        policy = HITLPolicy(require_approval_on=[RiskTier.HIGH])
        guard = ComplianceGuard(classifier, policy, auditor)

        agent = Agent(llm=llm, tools=[...], middlewares=[guard])
    """

    def __init__(
        self,
        classifier: RiskClassifier | None = None,
        hitl_policy: HITLPolicy | None = None,
        auditor: ComplianceAuditor | None = None,
    ):
        self._classifier = classifier or RiskClassifier()
        self._hitl = hitl_policy or HITLPolicy()
        self._auditor = auditor
        self._risk_tier: RiskTier | None = None
        self._agent_name: str = "unknown"

    @property
    def risk_tier(self) -> RiskTier | None:
        """The classified risk tier (available after first invocation)."""
        return self._risk_tier

    async def __call__(
        self,
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        # Classify on first call
        if self._risk_tier is None:
            tools = [t.name for t in ctx.get("tools", [])]
            labels = ctx.get("data_labels", [])
            domain = ctx.get("domain")
            self._risk_tier, matched = self._classifier.classify(
                tools, labels, domain,
            )
            self._agent_name = ctx.get("agent_name", "unknown")

            triggers = [r.reason for r in matched]
            logger.info(
                f"Compliance: risk={self._risk_tier.value}, "
                f"triggers={triggers}"
            )

            if self._auditor:
                self._auditor.record("risk_classification", {
                    "risk_tier": self._risk_tier.value,
                    "triggers": triggers,
                })

        # HITL gate
        if self._hitl.needs_approval(self._risk_tier):
            last_msg = messages[-1].content if messages else ""
            req = ApprovalRequest(
                request_id=f"hitl-{ctx.get('run_id', '')}",
                agent_name=self._agent_name,
                action=str(last_msg)[:200],
                risk_tier=self._risk_tier,
                reason=f"Risk tier: {self._risk_tier.value}",
            )

            if self._auditor:
                self._auditor.record("hitl_required", req.model_dump())

            if self._hitl.approval_handler:
                approved = await self._hitl.approval_handler(req)
                if not approved:
                    if self._auditor:
                        self._auditor.record("hitl_denied", {
                            "request_id": req.request_id,
                        })
                    yield StreamEvent(
                        type=EventType.error,
                        content="Human approval denied",
                        data={"reason": "hitl_denied"},
                    )
                    return
                if self._auditor:
                    self._auditor.record("hitl_approved", {
                        "request_id": req.request_id,
                    })
            else:
                logger.warning(
                    "HITL required but no approval_handler configured. "
                    "Blocking request."
                )
                yield StreamEvent(
                    type=EventType.error,
                    content="Human approval required but no handler configured",
                    data={"reason": "hitl_no_handler"},
                )
                return

        async for event in next_handler(messages, ctx):
            yield event
