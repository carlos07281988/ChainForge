# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Chaos engineering for agent simulation.

Provides configuration and injection of controlled failures, latency jitter,
and model errors to stress-test agent resilience.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChaosConfig:
    """Configuration for chaos injection during agent simulation.

    Attributes:
        tool_failure_rate: Probability (0.0–1.0) that a tool call will fail.
        latency_jitter_ms: Maximum additional latency in milliseconds.
        model_error_rate: Probability (0.0–1.0) that the model returns an error.
    """

    tool_failure_rate: float = 0.05
    latency_jitter_ms: int = 500
    model_error_rate: float = 0.02

    def __post_init__(self) -> None:
        # Clamp to valid ranges.
        self.tool_failure_rate = max(0.0, min(1.0, self.tool_failure_rate))
        self.model_error_rate = max(0.0, min(1.0, self.model_error_rate))
        self.latency_jitter_ms = max(0, self.latency_jitter_ms)


@dataclass
class ChaosInjector:
    """Middleware-style chaos injector for agent calls.

    Wraps agent invocation points and randomly injects failures,
    latency, or model errors based on the provided ChaosConfig.

    Attributes:
        config: The chaos configuration controlling injection probabilities.
    """

    config: ChaosConfig

    # Internal tracking counters.
    _tool_failures: int = field(default=0, repr=False)
    _latency_injections: int = field(default=0, repr=False)
    _model_errors: int = field(default=0, repr=False)
    _total_checks: int = field(default=0, repr=False)

    def apply(self, event_or_call: str) -> bool:
        """Determine whether chaos should be injected for a given event.

        Args:
            event_or_call: A string identifier for the event or call type.
                           Typical values: 'tool_call', 'model_call', 'any'.

        Returns:
            True if chaos should be injected for this event, False otherwise.
        """
        self._total_checks += 1
        roll = random.random()

        if event_or_call in ("tool_call", "any"):
            if roll < self.config.tool_failure_rate:
                self._tool_failures += 1
                return True

        if event_or_call in ("model_call", "any"):
            if roll < self.config.model_error_rate:
                self._model_errors += 1
                return True

        return False

    async def inject_latency(self) -> float:
        """Inject a random latency delay if chaos activates.

        Returns:
            The actual delay applied in milliseconds.
        """
        roll = random.random()
        if roll < 0.5:
            # 50% chance of latency injection per call.
            jitter = random.uniform(0, self.config.latency_jitter_ms) / 1000.0
            self._latency_injections += 1
            await asyncio.sleep(jitter)
            return jitter * 1000
        return 0.0

    def simulate_tool_failure(self, tool_name: str) -> dict[str, Any]:
        """Generate a simulated tool failure response.

        Args:
            tool_name: The name of the tool that "failed".

        Returns:
            A dictionary representing a failure response.
        """
        return {
            "error": True,
            "tool": tool_name,
            "message": f"[CHAOS] Simulated failure for tool '{tool_name}'",
            "chaos_injected": True,
        }

    def simulate_model_error(self) -> dict[str, Any]:
        """Generate a simulated model error response.

        Returns:
            A dictionary representing a model error.
        """
        error_types = [
            "rate_limit_exceeded",
            "context_length_exceeded",
            "service_unavailable",
            "timeout",
        ]
        return {
            "error": True,
            "type": random.choice(error_types),
            "message": "[CHAOS] Simulated model error",
            "chaos_injected": True,
        }

    def stats(self) -> dict:
        """Return injection statistics.

        Returns:
            A dictionary with tool_failures, latency_injections,
            model_errors, and total_checks counts.
        """
        return {
            "tool_failures": self._tool_failures,
            "latency_injections": self._latency_injections,
            "model_errors": self._model_errors,
            "total_checks": self._total_checks,
        }

    def reset(self) -> None:
        """Reset all injection counters to zero."""
        self._tool_failures = 0
        self._latency_injections = 0
        self._model_errors = 0
        self._total_checks = 0

    def __repr__(self) -> str:
        return (
            f"ChaosInjector(tool_fail={self.config.tool_failure_rate:.0%}, "
            f"jitter={self.config.latency_jitter_ms}ms, "
            f"model_err={self.config.model_error_rate:.0%})"
        )
