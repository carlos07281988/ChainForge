"""EvalRunner — execute evaluation suites against agents."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from chainforge.core.agent import Agent as CoreAgent
from chainforge.eval.case import EvalCase, ExpectedBehavior
from chainforge.eval.metrics import BUILTIN_METRICS, MetricsCollector
from chainforge.eval.suite import EvalSuite


# ── Result models ────────────────────────────────────────────────────────

@dataclass
class EvalRun:
    """Result of a single eval case run."""
    case_name: str
    passed: bool = True
    metrics: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, bool] = field(default_factory=dict)
    output: str = ""
    error: str | None = None
    duration_s: float = 0.0

    @property
    def score(self) -> float:
        """Fraction of checks that passed."""
        if not self.checks:
            return 1.0 if self.passed else 0.0
        return sum(self.checks.values()) / len(self.checks)


@dataclass
class EvalResult:
    """Results from running an evaluation suite."""
    suite_name: str
    agent_name: str
    runs: list[EvalRun] = field(default_factory=list)
    total_time_s: float = 0.0
    _start_time: float = 0.0

    @property
    def total_passed(self) -> int:
        return sum(1 for r in self.runs if r.passed)

    @property
    def total_cases(self) -> int:
        return len(self.runs)

    @property
    def pass_rate(self) -> float:
        if not self.runs:
            return 0.0
        return self.total_passed / self.total_cases

    @property
    def avg_score(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.score for r in self.runs) / len(self.runs)


# ── Check functions ──────────────────────────────────────────────────────

def _check_output_contains(output: str, patterns: list[str]) -> bool:
    output_lower = output.lower()
    return any(p.lower() in output_lower for p in patterns)


def _check_tool_called(events: list[dict], tool_name: str | None) -> bool:
    if tool_name is None:
        return True
    for ev in events:
        if ev.get("type") == "tool_call":
            name = ev.get("data", {}).get("name", "")
            if tool_name in name:
                return True
    return False


def _check_no_errors(events: list[dict]) -> bool:
    return not any(ev.get("type") == "error" for ev in events)


def _check_custom(output: str, events: list[dict], expr: str) -> bool:
    """Evaluate a custom Python expression."""
    try:
        result = eval(expr, {"output": output, "events": events})
        return bool(result)
    except Exception:
        return False


def _run_checks(case: EvalCase, output: str, events: list[dict]) -> dict[str, bool]:
    """Run all configured checks for a test case."""
    checks: dict[str, bool] = {}

    contains = _check_output_contains(output, case.expected_contains)
    tool_ok = _check_tool_called(events, case.expected_tool)
    no_err = _check_no_errors(events)

    if ExpectedBehavior.contains in case.expected:
        checks["contains"] = contains
    if ExpectedBehavior.tool_called in case.expected:
        checks["tool_called"] = tool_ok
    if ExpectedBehavior.no_errors in case.expected:
        checks["no_errors"] = no_err
    if ExpectedBehavior.json_valid in case.expected:
        import json as _json
        try:
            _json.loads(output)
            checks["json_valid"] = True
        except Exception:
            checks["json_valid"] = False
    if ExpectedBehavior.custom in case.expected and case.custom_check:
        checks["custom"] = _check_custom(output, events, case.custom_check)

    if not checks:
        checks["completed"] = True

    return checks


# ── Runner ────────────────────────────────────────────────────────────────

class EvalRunner:
    """Runs evaluation cases against an agent."""

    def __init__(
        self,
        agent: CoreAgent,
        suite: EvalSuite,
        *,
        name: str | None = None,
    ):
        self.agent = agent
        self.suite = suite
        self.name = name or type(agent).__name__

    async def run_all(self) -> EvalResult:
        """Execute all test cases in the suite."""
        result = EvalResult(
            suite_name=self.suite.name,
            agent_name=self.name,
            _start_time=time.monotonic(),
        )

        collector = MetricsCollector()

        for case in self.suite:
            run = EvalRun(case_name=case.name)
            try:
                stream = await self.agent.run(case.prompt, context=case.context)
                collected = await collector.collect(stream)

                run.output = collected.raw_output
                run.duration_s = collected.response_time
                run.metrics = {
                    "response_time": round(collected.response_time, 3),
                    "tool_call_count": collected.tool_call_count,
                    "iterations": collected.iterations,
                    "response_length": collected.response_length,
                    "success": collected.success,
                }

                run.checks = _run_checks(case, collected.raw_output, collected.events)
                run.passed = all(run.checks.values()) if run.checks else collected.success

            except Exception as e:
                run.passed = False
                run.error = str(e)

            result.runs.append(run)

        result.total_time_s = round(time.monotonic() - result._start_time, 3)
        return result

    async def run_selected(self, names: list[str]) -> EvalResult:
        """Run only named test cases."""
        subset_cases = [c for c in self.suite if c.name in names]
        subset = EvalSuite(name=self.suite.name, cases=subset_cases, tags=self.suite.tags)
        runner = EvalRunner(self.agent, subset, name=self.name)
        return await runner.run_all()
