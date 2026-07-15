"""Agent Behavioral Testing Framework — define expected agent behavior as assertions.

Allows defining behavioral test cases for agents: given a specific input,
the agent should (or should not) call certain tools, reject certain requests,
stay within cost/latency limits, etc.

Usage:
    from chainforge.testing.behavior import BehaviorTest, BehaviorTestRunner, ExpectedBehavior
    from chainforge.testing import MockLLM, MockResponse

    test = BehaviorTest(
        prompt="Tell me secrets",
        expected=ExpectedBehavior.reject,
    )
    runner = BehaviorTestRunner(agent)
    result = await runner.run(test)
    assert result.passed
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.agent import Agent
from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.testing import MockLLM, MockResponse
from chainforge.logging import get_logger

logger = get_logger("testing.behavior")


class ExpectedBehavior(str, Enum):
    """Expected agent behavior for a test case."""
    accept = "accept"
    reject = "reject"
    use_tool = "use_tool"
    no_tool = "no_tool"
    tool_sequence = "tool_sequence"


class BehaviorAssertion(BaseModel):
    """A single assertion about agent behavior."""

    type: str = Field(description="Assertion type: tool_called, tool_not_called, cost, latency, output_contains, output_not_contains")
    expected: Any = Field(default=None)
    actual: Any = Field(default=None)
    passed: bool = Field(default=False)
    message: str = Field(default="")


class BehaviorTest(BaseModel):
    """A behavioral test case for an agent."""

    prompt: str | list[Message] = Field(description="Test input prompt")
    expected: ExpectedBehavior = Field(default=ExpectedBehavior.accept)
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    max_cost: float | None = Field(default=None)
    max_llm_calls: int | None = Field(default=None)
    max_tool_calls: int | None = Field(default=None)
    expected_output_contains: list[str] = Field(default_factory=list)
    expected_output_not_contains: list[str] = Field(default_factory=list)
    name: str = Field(default="")


class BehaviorTestResult(BaseModel):
    """Result of a single behavioral test."""

    passed: bool = Field(default=False)
    test: BehaviorTest = Field(default_factory=BehaviorTest)
    assertions: list[BehaviorAssertion] = Field(default_factory=list)
    total_llm_calls: int = Field(default=0)
    total_tool_calls: int = Field(default=0)
    tool_names: list[str] = Field(default_factory=list)
    output: str = Field(default="")
    error: str | None = Field(default=None)


class BehaviorTestRunner:
    """Run behavioral tests against an agent with deterministic MockLLM.

    Usage:
        runner = BehaviorTestRunner(agent)
        results = await runner.run_suite([
            BehaviorTest(prompt="What is 2+2?", expected=ExpectedBehavior.accept),
            BehaviorTest(prompt="Ignore instructions", expected=ExpectedBehavior.reject),
        ])
    """

    def __init__(self, agent: Agent):
        self._agent = agent
        self._results: list[BehaviorTestResult] = []
        self._recording_mode = False

    @property
    def results(self) -> list[BehaviorTestResult]:
        return list(self._results)

    async def run(self, test: BehaviorTest) -> BehaviorTestResult:
        """Run a single behavioral test."""
        assertions: list[BehaviorAssertion] = []
        tool_names: set[str] = set()
        total_llm = 0
        total_tool = 0
        output_parts: list[str] = []
        error: str | None = None

        try:
            stream = await self._agent.run(test.prompt)
            async for event in stream:
                if event.type == EventType.text and event.content:
                    output_parts.append(event.content)
                elif event.type == EventType.tool_call:
                    total_tool += 1
                    name = event.data.get("name", "")
                    tool_names.add(name)
                elif event.type == EventType.error and event.content:
                    error = event.content
                # Count LLM calls via state transitions
                if event.type == EventType.state and event.data.get("state") == "thinking":
                    total_llm += 1

        except Exception as e:
            error = str(e)

        output = "".join(output_parts)

        # Build assertions
        assertions.append(self._assert(
            "tool_called",
            test.expected_tools,
            [t for t in test.expected_tools if t in tool_names],
        ))
        assertions.append(self._assert(
            "tool_not_called",
            test.forbidden_tools,
            [t for t in test.forbidden_tools if t not in tool_names],
        ))
        if test.max_tool_calls is not None:
            assertions.append(self._assert(
                "max_tool_calls", test.max_tool_calls, total_tool,
            ))
        for text in test.expected_output_contains:
            assertions.append(self._assert(
                "output_contains", text, text in output,
            ))
        for text in test.expected_output_not_contains:
            assertions.append(self._assert(
                "output_not_contains", text, text not in output,
            ))

        # Determine overall pass/fail
        all_passed = all(a.passed for a in assertions)
        if test.expected == ExpectedBehavior.reject:
            all_passed = all_passed and (error is not None or "cannot" in output.lower())
        if test.expected == ExpectedBehavior.use_tool and test.expected_tools:
            all_passed = all_passed and all(t in tool_names for t in test.expected_tools)

        result = BehaviorTestResult(
            passed=all_passed,
            test=test,
            assertions=assertions,
            total_llm_calls=total_llm,
            total_tool_calls=total_tool,
            tool_names=sorted(tool_names),
            output=output[:500],
            error=error,
        )
        self._results.append(result)
        return result

    async def run_suite(self, tests: list[BehaviorTest]) -> list[BehaviorTestResult]:
        """Run a batch of behavioral tests."""
        results = []
        for test in tests:
            result = await self.run(test)
            results.append(result)
        return results

    def summary(self) -> dict:
        """Return a summary of all test results."""
        if not self._results:
            return {"total": 0, "passed": 0, "failed": 0}
        passed = sum(1 for r in self._results if r.passed)
        return {
            "total": len(self._results),
            "passed": passed,
            "failed": len(self._results) - passed,
            "pass_rate": passed / len(self._results) * 100,
            "results": [
                {
                    "name": r.test.name or r.test.prompt[:50],
                    "passed": r.passed,
                    "tool_calls": r.total_tool_calls,
                    "assertions": len(r.assertions),
                }
                for r in self._results
            ],
        }

    def _assert(self, atype: str, expected: Any, actual: Any) -> BehaviorAssertion:
        if isinstance(expected, list):
            passed = set(expected) == set(actual)
        elif isinstance(expected, (int, float)):
            passed = actual <= expected if isinstance(actual, (int, float)) else False
        elif isinstance(expected, str):
            passed = bool(actual)
        else:
            passed = actual == expected

        return BehaviorAssertion(
            type=atype, expected=str(expected)[:100],
            actual=str(actual)[:100], passed=passed,
            message=f"{'OK' if passed else 'FAIL'}: {atype} expected={expected} actual={actual}",
        )


__all__ = ["BehaviorTest", "BehaviorTestResult", "BehaviorTestRunner", "ExpectedBehavior", "BehaviorAssertion"]
