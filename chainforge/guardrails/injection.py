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
"""Prompt injection detection guardrail.

Detects common prompt injection and jailbreak patterns:
  - Instruction override attempts
  - Role-play injection (DAN, etc.)
  - System prompt extraction
  - Encoding abuse (base64)
  - Harmful request patterns

Usage:
    guardrail = PromptInjectionGuardrail(sensitivity=0.7)
    result = await guardrail.check(user_input)
"""

from __future__ import annotations

import re
from typing import Any

from chainforge.guardrails.base import GuardrailResult, GuardrailAction, GuardrailSeverity

INJECTION_PATTERNS: list[tuple[str, str, float]] = [
    (r"ignore\s+(all\s+)?(previous\s+)?instructions?", "instruction_override", 0.9),
    (r"ignore\s+(all\s+)?(prior\s+)?(prompts?|commands?|directives?)", "instruction_override", 0.9),
    (r"disregard\s+(all\s+)?(previous\s+)?instructions?", "instruction_override", 0.85),
    (r"forget\s+(all\s+)?(previous\s+)?instructions?", "instruction_override", 0.85),
    (r"you\s+are\s+(now\s+)?(dan|free|unbounded|unleashed|unrestricted)", "role_play", 0.95),
    (r"new\s+(rule|rules|instruction|instructions)", "role_play", 0.8),
    (r"act\s+as\s+(if\s+you\s+are|though\s+you\s+are)\s+(a\s+)?(dan|free)", "role_play", 0.9),
    (r"pretend\s+(you\s+are|to\s+be)\s+(a\s+)?(dan|free|unbounded)", "role_play", 0.85),
    (r"(print|show|display|reveal|output)\s+(your\s+)?(system\s+)?(prompt|instructions?)", "prompt_leak", 0.9),
    (r"(what\s+are|tell\s+me)\s+(your\s+)?(initial\s+)?(prompt|instructions?)", "prompt_leak", 0.85),
    (r"repeat\s+(everything\s+)?(above|before|previously)", "prompt_leak", 0.8),
    (r"output\s+the\s+(above|initial|first)\s+(prompt|text|message)", "prompt_leak", 0.85),
    (r"(base64|base32|hex)\s+(decode|encode|decoded|encoded)", "encoding_abuse", 0.8),
    (r"system\s*(prompt|message|instruction)\s*:", "system_override", 0.7),
    (r"<\|im_start\|>|im_start|im_end", "token_injection", 0.9),
]

HARMFUL_PATTERNS: list[tuple[str, str, float]] = [
    (r"(how\s+to\s+)?(build|make|create)\s+(a\s+)?(bomb|weapon|explosive)", "harmful", 0.95),
    (r"(how\s+to\s+)?(hack|crack|bypass)\s+", "harmful", 0.9),
    (r"phishing\s+(email|page|site)", "harmful", 0.85),
]


class PromptInjectionGuardrail:
    """Detect prompt injection and jailbreak attempts via pattern matching."""

    def __init__(self, sensitivity: float = 0.7, name: str = "prompt_injection_guardrail"):
        self.sensitivity = sensitivity
        self.name = name

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text:
            return GuardrailResult(passed=True)

        text_lower = text.lower()
        max_risk = 0.0
        reasons = []
        categories: set[str] = set()

        for pattern, category, risk in INJECTION_PATTERNS + HARMFUL_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                max_risk = max(max_risk, risk)
                categories.add(category)
                reasons.append(f"Matched '{category}' (risk={risk})")

        if max_risk >= self.sensitivity:
            severity = (
                GuardrailSeverity.critical if max_risk >= 0.9
                else GuardrailSeverity.high if max_risk >= 0.8
                else GuardrailSeverity.medium
            )
            return GuardrailResult(
                passed=False,
                action=GuardrailAction.block,
                severity=severity,
                reason="; ".join(reasons[:3]),
                category=", ".join(sorted(categories)) or "injection",
                risk_score=max_risk,
                metadata={"matched": len(reasons), "sensitivity": self.sensitivity},
            )

        if max_risk > 0:
            return GuardrailResult(
                passed=True, action=GuardrailAction.warn,
                severity=GuardrailSeverity.low,
                reason=f"Low risk: {reasons[0] if reasons else 'unknown'}",
                category=", ".join(sorted(categories)) or "suspicious",
                risk_score=max_risk,
            )

        return GuardrailResult(passed=True, risk_score=0.0)


__all__ = ["PromptInjectionGuardrail"]
