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
"""Decision review — reconstruct and analyze the agent's decision process."""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.enterprise.justice.evidence import EvidencePack


class DecisionNode(BaseModel):
    """A node in the decision tree."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = ""
    label: str = ""
    type: str = ""
    children: list[str] = Field(default_factory=list)
    evidence_item_ids: list[str] = Field(default_factory=list)
    decision_rationale: str = ""


class DecisionTree(BaseModel):
    """Tree representation of the agent's decision process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    nodes: dict[str, DecisionNode] = Field(default_factory=dict)
    root_id: str = ""

    def to_mermaid(self) -> str:
        """Export as Mermaid flowchart for visualization."""
        lines = ["```mermaid", "graph TD"]
        for nid, node in self.nodes.items():
            safe_label = node.label.replace('"', "'")[:80]
            lines.append(f'    {nid}["{safe_label}"]')
            for child in node.children:
                lines.append(f"    {nid} --> {child}")
        lines.append("```")
        return "\n".join(lines)


class DecisionReview(BaseModel):
    """Complete review package for a contested decision."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    review_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_id: str = ""
    generated_at: float = Field(default_factory=time.time)
    appeal_reason: str = ""
    evidence: EvidencePack | None = None
    decision_tree: DecisionTree | None = None
    findings: list[str] = Field(default_factory=list)
    suggested_action: str = ""  # "uphold"|"overturn"|"review_recommended"
    risk_assessment: str = "low"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> dict:
        return self.model_dump()

    def summary(self) -> str:
        lines = [
            f"Decision Review: {self.review_id}",
            f"Run: {self.run_id}",
            f"Appeal: {self.appeal_reason[:200]}",
            f"Suggested: {self.suggested_action}",
            f"Risk: {self.risk_assessment}",
            "",
            "Findings:",
        ]
        for f in self.findings:
            lines.append(f"  • {f}")
        return "\n".join(lines)
