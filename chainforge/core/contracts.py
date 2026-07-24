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
"""Behavior Contract Runtime — execute and enforce ASL contracts at runtime.

Contracts define constraints on agent behavior, security, and performance.
The ContractEnforcer wraps an Agent and monitors execution against contracts,
emitting violations when constraints are breached.

Usage:
    from chainforge.core.contracts import (
        ContractRegistry, SecurityContract, PerformanceContract,
        ContractEnforcer,
    )

    contracts = ContractRegistry()
    contracts.add(SecurityContract(
        name="no_delete", rule="disallow_tool",
        tool_pattern="delete", severity="error",
    ))
    contracts.add(PerformanceContract(
        name="budget", rule="max_llm_calls",
        value=5, severity="warn",
    ))

    enforcer = ContractEnforcer(agent=my_agent, contracts=contracts)
    stream = await enforcer.run("Hello")
    report = enforcer.report()
"""

from __future__ import annotations

import fnmatch
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.logging import get_logger

logger = get_logger("core.contracts")


# ── ContractViolation ──────────────────────────────────────────────────────


class ContractViolation(BaseModel):
    """A record of a contract being violated during agent execution."""

    contract_name: str = Field(description="Name of the violated contract")
    rule: str = Field(description="Rule that was violated")
    severity: str = Field(description="error or warn")
    message: str = Field(description="Human-readable violation description")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    timestamp: float = Field(default_factory=time.time)


# ── Contract base ──────────────────────────────────────────────────────────


class Contract(BaseModel):
    """Base class for all behavior contracts.

    Subclasses define specific rules checked during agent execution.
    """

    name: str = Field(description="Contract identifier")
    description: str = Field(default="", description="Human-readable description")
    rule: str = Field(description="Rule identifier (disallow_tool, max_llm_calls, etc.)")
    severity: str = Field(default="error", description="error (blocks) or warn (logs only)")

    def check_tool(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> ContractViolation | None:
        """Check contract against a tool call. Override in subclasses."""
        return None

    def check_event(self, event: StreamEvent, run_context: dict[str, Any]) -> ContractViolation | None:
        """Check contract against a stream event. Override in subclasses."""
        return None

    def finalize(self, run_context: dict[str, Any]) -> list[ContractViolation]:
        """Check at end of execution. Override in subclasses."""
        return []


# ── SecurityContract ───────────────────────────────────────────────────────


class SecurityContract(Contract):
    """Security contract that restricts tool usage.

    Rules:
      - disallow_tool: Block tools matching a glob pattern.
      - max_calls_per_tool: Limit calls to a specific tool.
    """

    tool_pattern: str | None = Field(default=None, description="Glob pattern for tool names (e.g. 'delete_*')")
    max_calls: int | None = Field(default=None, description="Max calls per tool")
    target_tool: str | None = Field(default=None, description="Tool name (for max_calls_per_tool)")

    def check_tool(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> ContractViolation | None:
        if self.rule == "disallow_tool" and self.tool_pattern:
            if fnmatch.fnmatch(tool_name, self.tool_pattern):
                return ContractViolation(
                    contract_name=self.name,
                    rule=self.rule,
                    severity=self.severity,
                    message=f"Tool '{tool_name}' matches disallowed pattern '{self.tool_pattern}'",
                    details={"tool_name": tool_name, "pattern": self.tool_pattern, "args": tool_args or {}},
                )
        return None


# ── PerformanceContract ────────────────────────────────────────────────────


class PerformanceContract(Contract):
    """Performance/budget contract that limits resource usage.

    Rules:
      - max_llm_calls: Max LLM calls per run.
      - max_tool_calls: Max tool calls per run.
      - max_cost: Max estimated cost per run.
      - max_duration: Max execution duration in seconds.
    """

    value: float = Field(default=0.0, description="Threshold value")

    def finalize(self, run_context: dict[str, Any]) -> list[ContractViolation]:
        violations: list[ContractViolation] = []

        if self.rule == "max_llm_calls":
            actual = run_context.get("llm_calls", 0)
            if actual > self.value:
                violations.append(ContractViolation(
                    contract_name=self.name,
                    rule=self.rule,
                    severity=self.severity,
                    message=f"LLM calls ({actual}) exceeded limit ({self.value})",
                    details={"actual": actual, "limit": self.value},
                ))

        elif self.rule == "max_tool_calls":
            actual = run_context.get("tool_calls", 0)
            if actual > self.value:
                violations.append(ContractViolation(
                    contract_name=self.name,
                    rule=self.rule,
                    severity=self.severity,
                    message=f"Tool calls ({actual}) exceeded limit ({self.value})",
                    details={"actual": actual, "limit": self.value},
                ))

        elif self.rule == "max_cost":
            actual = run_context.get("cost", 0.0)
            if actual > self.value:
                violations.append(ContractViolation(
                    contract_name=self.name,
                    rule=self.rule,
                    severity=self.severity,
                    message=f"Cost ({actual:.4f}) exceeded budget ({self.value:.4f})",
                    details={"actual": actual, "limit": self.value},
                ))

        elif self.rule == "max_duration":
            start = run_context.get("start_time", time.time())
            actual = time.time() - start
            if actual > self.value:
                violations.append(ContractViolation(
                    contract_name=self.name,
                    rule=self.rule,
                    severity=self.severity,
                    message=f"Duration ({actual:.1f}s) exceeded limit ({self.value:.1f}s)",
                    details={"actual": round(actual, 1), "limit": self.value},
                ))

        return violations


# ── ContractRegistry ───────────────────────────────────────────────────────


class ContractRegistry(BaseModel):
    """Registry of contracts to enforce during agent execution.

    Usage:
        registry = ContractRegistry()
        registry.add(SecurityContract(name="no_delete", rule="disallow_tool", tool_pattern="delete"))
        registry.add(PerformanceContract(name="budget", rule="max_llm_calls", value=5))
    """

    _contracts: list[Contract] = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._contracts = []

    def add(self, contract: Contract) -> None:
        self._contracts.append(contract)

    def remove(self, name: str) -> bool:
        for i, c in enumerate(self._contracts):
            if c.name == name:
                self._contracts.pop(i)
                return True
        return False

    @property
    def all(self) -> list[Contract]:
        return list(self._contracts)

    @property
    def count(self) -> int:
        return len(self._contracts)

    def get(self, name: str) -> Contract | None:
        for c in self._contracts:
            if c.name == name:
                return c
        return None

    def check_tool(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> list[ContractViolation]:
        violations: list[ContractViolation] = []
        for c in self._contracts:
            v = c.check_tool(tool_name, tool_args)
            if v:
                violations.append(v)
        return violations

    def finalize_all(self, run_context: dict[str, Any]) -> list[ContractViolation]:
        violations: list[ContractViolation] = []
        for c in self._contracts:
            violations.extend(c.finalize(run_context))
        return violations


# ── ContractEnforcer ───────────────────────────────────────────────────────


class ContractEnforcer:
    """Wraps an Agent to enforce behavior contracts at runtime.

    Intercepts agent execution and monitors against all registered contracts.
    Security contracts block tool calls on error-severity violations.
    Performance contracts are checked after agent completion.

    Usage:
        contracts = ContractRegistry()
        contracts.add(SecurityContract(name="no_delete", rule="disallow_tool", tool_pattern="delete_*"))
        contracts.add(PerformanceContract(name="budget", rule="max_llm_calls", value=5))

        enforcer = ContractEnforcer(agent=my_agent, contracts=contracts)
        stream = await enforcer.run("Hello")
        report = enforcer.report()
    """

    def __init__(self, agent: Agent, contracts: ContractRegistry | None = None):
        self._agent = agent
        self._contracts = contracts or ContractRegistry()
        self._violations: list[ContractViolation] = []
        self._llm_calls = 0
        self._tool_calls = 0
        self._start_time = time.time()
        self._cost = 0.0

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def violations(self) -> list[ContractViolation]:
        return list(self._violations)

    async def run(self, prompt: str | list[Message], *,
                   context: dict[str, Any] | None = None,
                   **kwargs: Any) -> AsyncIterator[StreamEvent]:
        """Run the agent with contract enforcement.

        Args:
            prompt: User prompt or messages.
            context: Optional context.
            **kwargs: Additional args passed to Agent.run().

        Yields:
            StreamEvents with possible enforcement actions.
        """
        self._violations = []
        self._llm_calls = 0
        self._tool_calls = 0
        self._start_time = time.time()
        self._cost = 0.0

        stream = await self._agent.run(prompt, context=context, **kwargs)

        async for event in stream:
            # Check tool calls before they execute
            if event.type == EventType.tool_call:
                tool_name = event.data.get("name", "")
                tool_args = event.data.get("args", {})
                violations = self._contracts.check_tool(tool_name, tool_args)

                for v in violations:
                    self._violations.append(v)
                    logger.warning(f"Contract '{v.contract_name}' violated: {v.message}")

                    if v.severity == "error":
                        # Block the tool call — emit error instead
                        yield StreamEvent(
                            type=EventType.error,
                            content=f"Contract violation: {v.message}",
                            data={"violation": v.model_dump()},
                        )
                        # Skip the original event
                        continue

                self._tool_calls += 1

            elif event.type == EventType.text:
                self._llm_calls += 1

            yield event

    def report(self) -> dict[str, Any]:
        """Get a report of all contract violations.

        Returns:
            dict with violations, contracts checked, pass/fail status.
        """
        # Run finalization checks
        run_context = {
            "llm_calls": self._llm_calls,
            "tool_calls": self._tool_calls,
            "cost": self._cost,
            "start_time": self._start_time,
        }
        final_violations = self._contracts.finalize_all(run_context)
        self._violations.extend(final_violations)

        error_count = sum(1 for v in self._violations if v.severity == "error")
        warn_count = sum(1 for v in self._violations if v.severity == "warn")

        return {
            "passed": error_count == 0,
            "total_violations": len(self._violations),
            "errors": error_count,
            "warnings": warn_count,
            "contracts_checked": self._contracts.count,
            "violations": [v.model_dump() for v in self._violations],
        }


__all__ = [
    "Contract",
    "ContractViolation",
    "ContractRegistry",
    "SecurityContract",
    "PerformanceContract",
    "ContractEnforcer",
]
