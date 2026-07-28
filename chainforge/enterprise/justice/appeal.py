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
"""Appeal lifecycle — submit, review, and resolve human challenges to agent decisions."""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.justice.review import DecisionReview


class AppealRequest(BaseModel):
    """A user-initiated appeal against an agent decision."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    appeal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str = ""
    reason: str = ""
    raised_by: str = ""
    created_at: float = Field(default_factory=time.time)
    severity: str = "medium"  # low|medium|high|critical
    evidence_requested: bool = True  # auto-generate DecisionReview


class AppealVerdict(BaseModel):
    """Result of a human-reviewed appeal."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    appeal_id: str = ""
    reviewed_by: str = ""
    reviewed_at: float = Field(default_factory=time.time)
    upheld: bool = False  # True = original decision was correct, False = overturned
    override_action: str = ""  # What to do instead
    reason: str = ""
    evidence_used: list[str] = Field(default_factory=list)


class AppealEngine:
    """Manages the complete appeal lifecycle: submit, route, verify, record.

    Usage::

        engine = AppealEngine()
        review = engine.generate_review(appeal, evidence_pack)
        verdict = await engine.human_appeal(appeal, "reviewer@acme.com", review)
    """

    def __init__(self):
        self._appeals: dict[str, AppealRequest] = {}
        self._reviews: dict[str, DecisionReview] = {}
        self._verdicts: dict[str, AppealVerdict] = {}

    def submit(self, appeal: AppealRequest) -> AppealRequest:
        """Register an appeal for processing."""
        self._appeals[appeal.appeal_id] = appeal
        return appeal

    def generate_review(
        self,
        appeal: AppealRequest,
        evidence: Any,
        decision_tree: Any = None,
    ) -> DecisionReview:
        """Generate a DecisionReview from evidence."""
        findings: list[str] = []
        risk = "low"
        if evidence and hasattr(evidence, "items"):
            tool_calls = [i for i in evidence.items if i.event_type == "tool_call"]
            if tool_calls:
                names = ", ".join(t.tool_name for t in tool_calls)
                findings.append(f"Agent used {len(tool_calls)} tool call(s): {names}")
            errors = [i for i in evidence.items if i.event_type == "error"]
            if errors:
                findings.append(f"Agent encountered {len(errors)} error(s)")
                risk = "medium"
        review = DecisionReview(
            run_id=appeal.run_id,
            appeal_reason=appeal.reason,
            evidence=evidence,
            decision_tree=decision_tree,
            findings=findings,
            risk_assessment=risk,
            suggested_action="human_review" if risk != "low" else "uphold",
        )
        self._reviews[appeal.appeal_id] = review
        return review

    async def human_appeal(
        self, appeal: AppealRequest, assigned_to: str, review: DecisionReview
    ) -> AppealVerdict:
        """Record a human appeal verdict (stub — production integrates ticketing/email)."""
        verdict = AppealVerdict(
            appeal_id=appeal.appeal_id,
            reviewed_by=assigned_to,
            upheld=False,
            reason="Pending human review",
            override_action="review_recommended",
        )
        self._verdicts[appeal.appeal_id] = verdict
        return verdict

    def record_verdict(self, verdict: AppealVerdict) -> None:
        """Store a finalized verdict."""
        self._verdicts[verdict.appeal_id] = verdict

    def get_appeal(self, appeal_id: str) -> AppealRequest | None:
        return self._appeals.get(appeal_id)

    def get_review(self, appeal_id: str) -> DecisionReview | None:
        return self._reviews.get(appeal_id)

    def get_verdict(self, appeal_id: str) -> AppealVerdict | None:
        return self._verdicts.get(appeal_id)

    @property
    def stats(self) -> dict:
        appeals = list(self._appeals.values())
        verdicts = list(self._verdicts.values())
        return {
            "total_appeals": len(appeals),
            "total_verdicts": len(verdicts),
            "upheld": sum(1 for v in verdicts if v.upheld),
            "overturned": sum(1 for v in verdicts if not v.upheld),
            "pending": sum(1 for a in appeals if a.appeal_id not in self._verdicts),
        }
