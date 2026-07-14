# Copyright 2024 ChainForge Contributors
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
"""Output guardrails — content safety, PII leak prevention, quality checks."""

from __future__ import annotations

import re
from typing import Any

from chainforge.guardrails.base import (
    GuardrailResult,
    GuardrailSeverity,
    block_result,
    flag_result,
    pass_result,
)
from chainforge.logging import get_logger

logger = get_logger("guardrails.output")


# ── PII Leak Prevention ────────────────────────────────────────────────────


_OUTPUT_PII_PATTERNS: list[tuple[str, str, GuardrailSeverity]] = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn", GuardrailSeverity.high),
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "credit_card", GuardrailSeverity.high),
    (r"\b(sk-[a-zA-Z0-9]{20,}|pk-[a-zA-Z0-9]{20,})\b", "api_key", GuardrailSeverity.critical),
    (r"(?i)(password|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]", "credential_leak", GuardrailSeverity.critical),
]


class PIILeakGuard:
    """Detect PII / secrets in agent outputs before sending to user.

    Args:
        action: "block" (default) — prevent output, "flag" — allow with warning.
    """

    name: str = "pii_leak_guard"

    def __init__(self, action: str = "block"):
        self.patterns = _OUTPUT_PII_PATTERNS
        self.action = action

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text:
            return pass_result(category="pii_leak")

        for pattern, category, severity in self.patterns:
            match = re.search(pattern, text)
            if match:
                logger.warning(f"PII leak detected in output [{category}]")
                if self.action == "block":
                    return block_result(
                        reason=f"Output contains sensitive data: {category}",
                        category=category,
                        severity=severity,
                        metadata={"detected_type": category},
                    )
                return flag_result(
                    reason=f"Output may contain {category}",
                    category=category,
                    severity=severity,
                )

        return pass_result(category="pii_leak")


# ── Content Safety ─────────────────────────────────────────────────────────


_HARMFUL_PATTERNS: list[tuple[str, str, GuardrailSeverity]] = [
    (r"(?i)(self[-\s]?harm|suicide|kill\s+yourself)", "self_harm", GuardrailSeverity.critical),
    (r"(?i)(hate\s+speech|racial\s+slur|discriminat)", "hate_speech", GuardrailSeverity.high),
    (r"(?i)(bomb|explosive|weapon\s+instructions|how\s+to\s+make\s+)", "dangerous", GuardrailSeverity.high),
    (r"(?i)(child\s+abuse|exploit)", "child_safety", GuardrailSeverity.critical),
]


class ContentSafetyGuard:
    """Detect harmful, illegal, or unsafe content in outputs.

    This is a pattern-based baseline. For production systems,
    pair with an LLM-based content moderation API.
    """

    name: str = "content_safety"

    def __init__(self, action: str = "block"):
        self.patterns = _HARMFUL_PATTERNS
        self.action = action

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text:
            return pass_result(category="content_safety")

        for pattern, category, severity in self.patterns:
            match = re.search(pattern, text)
            if match:
                logger.warning(f"Harmful content detected [{category}]")
                return block_result(
                    reason=f"Output contains prohibited content: {category}",
                    category=category,
                    severity=severity,
                )

        return pass_result(category="content_safety")


# ── Gibberish / Quality Check ──────────────────────────────────────────────


class QualityGuard:
    """Basic quality check — detect empty, repetitive, or very short responses.

    Args:
        min_length: Minimum expected response length (default 5).
        max_repetition_ratio: Max ratio of repeated n-grams (default 0.8).
    """

    name: str = "quality_guard"

    def __init__(self, min_length: int = 5, max_repetition_ratio: float = 0.8):
        self.min_length = min_length
        self.max_repetition_ratio = max_repetition_ratio

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text or len(text.strip()) < self.min_length:
            return flag_result(
                reason=f"Response too short ({len(text.strip())} chars, min {self.min_length})",
                category="quality",
                severity=GuardrailSeverity.low,
            )

        # Check for excessive repetition (simple bigram overlap)
        words = text.split()
        if len(words) >= 5:
            bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
            unique = set(bigrams)
            if len(bigrams) > 0 and len(unique) / len(bigrams) < (1 - self.max_repetition_ratio):
                return flag_result(
                    reason="Response appears overly repetitive",
                    category="quality",
                    severity=GuardrailSeverity.low,
                )

        return pass_result(category="quality")
