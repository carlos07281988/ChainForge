"""Input guardrails — detect prompt injection, sensitive data, topic violations."""

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

logger = get_logger("guardrails.input")


# ── Injection Detection ─────────────────────────────────────────────────────


_INJECTION_PATTERNS: list[tuple[str, str, GuardrailSeverity]] = [
    # Direct prompt injection
    (r"(?i)(ignore|disregard|forget|override)\s+(all\s+)?(previous|above|prior)", "injection", GuardrailSeverity.high),
    (r"(?i)(you\s+are\s+(not|now).*?(instead|actually))", "injection", GuardrailSeverity.high),
    (r"(?i)(system\s*(prompt|instruction|message).*?(override|change))", "injection", GuardrailSeverity.high),
    (r"(?i)(new\s+(instruction|direction|rule).*?follow)", "injection", GuardrailSeverity.medium),
    (r"(?i)(DAN|do\s+anything\s+now|jailbreak)", "injection", GuardrailSeverity.critical),
    # Unauthorized command execution
    (r"(?i)(execute|run)\s+(shell|bash|command|cmd)", "command_injection", GuardrailSeverity.high),
    (r"(?i)(read|write|delete|modify)\s+(file|system|config)", "command_injection", GuardrailSeverity.medium),
    # Data extraction attempts
    (r"(?i)(export|dump|extract|steal|leak)\s+(all|entire|everything)", "data_exfiltration", GuardrailSeverity.high),
    (r"(?i)(api[_\s]?key|password|secret|token|credential)", "sensitive", GuardrailSeverity.low),
]


class InjectionDetector:
    """Detect prompt injection and jailbreak attempts.

    Uses pattern matching for known attack signatures.
    For production, pair with an LLM-based detector.
    """

    name: str = "injection_detector"
    patterns: list[tuple[str, str, GuardrailSeverity]] = _INJECTION_PATTERNS

    def __init__(self, patterns: list[tuple[str, str, GuardrailSeverity]] | None = None):
        if patterns is not None:
            self.patterns = patterns

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text:
            return pass_result(category="injection")

        for pattern, category, severity in self.patterns:
            match = re.search(pattern, text)
            if match:
                matched_text = match.group(0)[:80]
                logger.warning(f"Injection detected [{severity.value}]: {matched_text}")
                if severity in (GuardrailSeverity.high, GuardrailSeverity.critical):
                    return block_result(
                        reason=f"Potential injection: '{matched_text}'",
                        category=category,
                        severity=severity,
                        metadata={"matched": matched_text, "pattern": pattern},
                    )
                return flag_result(
                    reason=f"Suspicious input: '{matched_text}'",
                    category=category,
                    severity=severity,
                )

        return pass_result(category="injection")


# ── Topic Filter ────────────────────────────────────────────────────────────


class TopicFilter:
    """Restrict conversations to allowed topics.

    Args:
        allowed: List of allowed topics (substring match). Empty = allow all.
        blocked: List of blocked topics (substring match). Empty = block none.
    """

    name: str = "topic_filter"

    def __init__(
        self,
        allowed: list[str] | None = None,
        blocked: list[str] | None = None,
    ):
        self.allowed = [a.lower() for a in allowed] if allowed else []
        self.blocked = [b.lower() for b in blocked] if blocked else []

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text:
            return pass_result(category="topic")

        lower = text.lower()

        # Check blocked topics first
        for topic in self.blocked:
            if topic in lower:
                logger.warning(f"Blocked topic detected: {topic}")
                return block_result(
                    reason=f"Topic '{topic}' is not allowed",
                    category="topic",
                    severity=GuardrailSeverity.medium,
                    metadata={"blocked_topic": topic},
                )

        # If allowed list is non-empty, check that at least one matches
        if self.allowed:
            for topic in self.allowed:
                if topic in lower:
                    return pass_result(category="topic")
            logger.warning(f"Input does not match any allowed topic: {self.allowed}")
            return block_result(
                reason=f"Input must relate to one of: {', '.join(self.allowed)}",
                category="topic",
                severity=GuardrailSeverity.low,
            )

        return pass_result(category="topic")


# ── Sensitive Data Filter (Input) ──────────────────────────────────────────


_SENSITIVE_PATTERNS: list[tuple[str, str, GuardrailSeverity]] = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn", GuardrailSeverity.high),
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "credit_card", GuardrailSeverity.high),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "email", GuardrailSeverity.medium),
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "ip_address", GuardrailSeverity.low),
    (r"\b(sk-[a-zA-Z0-9]{20,}|pk-[a-zA-Z0-9]{20,})\b", "api_key", GuardrailSeverity.critical),
]


class SensitiveDataFilter:
    """Detect personally identifiable information (PII) in inputs.

    By default runs in 'flag' mode — allows but logs the detection.
    Set action='block' to reject inputs containing PII.
    """

    name: str = "sensitive_data_filter"

    def __init__(
        self,
        patterns: list[tuple[str, str, GuardrailSeverity]] | None = None,
        action: str = "flag",
    ):
        self.patterns = patterns or _SENSITIVE_PATTERNS
        self.action = action

    async def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        if not text:
            return pass_result(category="sensitive_data")

        for pattern, category, severity in self.patterns:
            match = re.search(pattern, text)
            if match:
                logger.warning(f"Sensitive data detected [{category}]")
                if self.action == "block" and severity in (GuardrailSeverity.high, GuardrailSeverity.critical):
                    return block_result(
                        reason=f"Sensitive data detected: {category}",
                        category=category,
                        severity=severity,
                    )
                return flag_result(
                    reason=f"Sensitive data detected: {category}",
                    category=category,
                    severity=severity,
                )

        return pass_result(category="sensitive_data")
