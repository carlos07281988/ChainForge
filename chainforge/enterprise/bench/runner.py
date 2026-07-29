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
"""BenchmarkRunner — execute suites, validate expectations, and compare agent runs."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.enterprise.bench.suite import BenchmarkScenario, BenchmarkSuite
from chainforge.core.stream import EventType


class BenchmarkResult(BaseModel):
    """Result of running a single scenario against an agent."""

    scenario: str = ""
    passed: bool = False
    latency_ms: float = 0.0
    cost: float = 0.0
    tokens: int = 0
    tool_calls_made: list[str] = Field(default_factory=list)
    output: str = ""
    error: str | None = None
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)


class BenchmarkComparison(BaseModel):
    """A/B comparison of two agent runs on the same scenario."""

    scenario: str = ""
    a: BenchmarkResult | None = None  # agent A (baseline)
    b: BenchmarkResult | None = None  # agent B (candidate)
    winner: str = ""  # "a"|"b"|"tie"
    advantage: str = ""  # Why the winner won


class BenchmarkRunner:
    """Run benchmarks and compare agent performance.

    Usage:
        suite = BenchmarkSuite.load("bench.yaml")
        runner = BenchmarkRunner(suite)
        result = await runner.run(agent, scenario="refund_request")
        comparison = await runner.compare(agent_v1, agent_v2, "refund_request")
    """

    def __init__(self, suite: BenchmarkSuite) -> None:
        self._suite = suite

    async def run(
        self, agent: Any, scenario: str | None = None, **opts: Any
    ) -> BenchmarkResult | list[BenchmarkResult]:
        """Run benchmark scenarios against an agent."""
        scenarios = [s for s in self._suite.scenarios if scenario is None or s.name == scenario]
        results = []
        for sc in scenarios:
            result = await self._run_scenario(agent, sc, **opts)
            results.append(result)
        return results[0] if scenario and len(results) == 1 else results

    async def _run_scenario(
        self, agent: Any, sc: BenchmarkScenario, **opts: Any
    ) -> BenchmarkResult:
        """Execute a single scenario against an agent (production runs actual agent)."""
        start = time.time()
        tool_calls: list[str] = []
        output = ""
        error = None
        try:
            stream = await agent.run(sc.input)
            async for event in stream:
                if hasattr(event, "type"):
                    if event.type == EventType.tool_call:
                        tn = event.data.get("tool_name", "") if event.data else ""
                        if tn:
                            tool_calls.append(tn)
                    elif event.type == EventType.text:
                        output += (
                            str(event.data.get("content", "") if event.data else event)
                            if event.data
                            else str(event)
                        )
                elif hasattr(event, "content") and event.content:
                    output += str(event.content)
                    if hasattr(event, "cost"):
                        pass  # capture cost if available
        except Exception as e:
            error = str(e)
        latency = (time.time() - start) * 1000
        checks_passed, checks_failed = self._check(sc, tool_calls, output, latency, 0.0)
        return BenchmarkResult(
            scenario=sc.name,
            passed=len(checks_failed) == 0,
            latency_ms=latency,
            cost=0.0,
            tokens=0,
            tool_calls_made=tool_calls,
            output=output[:500],
            error=error,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )

    def _check(
        self,
        sc: BenchmarkScenario,
        tool_calls: list[str],
        output: str,
        latency_ms: float,
        cost: float,
    ) -> tuple[list[str], list[str]]:
        passed: list[str] = []
        failed: list[str] = []
        exp = sc.expect
        for t in exp.tool_calls_include:
            if t in tool_calls:
                passed.append(f"tool_called:{t}")
            else:
                failed.append(f"tool_not_called:{t}")
        for t in exp.tool_calls_exclude:
            if t not in tool_calls:
                passed.append(f"tool_avoided:{t}")
            else:
                failed.append(f"tool_called_forbidden:{t}")
        for s in exp.output_contains:
            if s.lower() in output.lower():
                passed.append(f"output_contains:{s}")
            else:
                failed.append(f"output_missing:{s}")
        for s in exp.output_not_contains:
            if s.lower() not in output.lower():
                passed.append(f"output_excludes:{s}")
            else:
                failed.append(f"output_contains_forbidden:{s}")
        if exp.max_latency_ms and latency_ms <= exp.max_latency_ms:
            passed.append("latency_ok")
        elif exp.max_latency_ms:
            failed.append(f"latency_too_high:{latency_ms:.0f}ms>{exp.max_latency_ms}ms")
        if exp.max_cost and cost <= exp.max_cost:
            passed.append("cost_ok")
        elif exp.max_cost:
            failed.append(f"cost_too_high:${cost:.4f}>${exp.max_cost:.4f}")
        return passed, failed

    async def compare(
        self, agent_a: Any, agent_b: Any, scenario: str
    ) -> BenchmarkComparison:
        """Compare two agents on the same benchmark scenario (A/B test)."""
        result_a = await self.run(agent_a, scenario=scenario)
        result_b = await self.run(agent_b, scenario=scenario)
        if not isinstance(result_a, BenchmarkResult):
            result_a = result_a[0]
        if not isinstance(result_b, BenchmarkResult):
            result_b = result_b[0]
        score_a = len(result_a.checks_passed) - len(result_a.checks_failed)
        score_b = len(result_b.checks_passed) - len(result_b.checks_failed)
        if score_a > score_b:
            winner = "a"
            advantage = f"Agent A passed {score_a - score_b} more checks"
        elif score_b > score_a:
            winner = "b"
            advantage = f"Agent B passed {score_b - score_a} more checks"
        else:
            winner = "tie"
            advantage = "Equal performance"
        return BenchmarkComparison(
            scenario=scenario, a=result_a, b=result_b, winner=winner, advantage=advantage
        )
