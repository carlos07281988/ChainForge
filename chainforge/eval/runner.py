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


import ast

class _SafeExprEvaluator(ast.NodeVisitor):
    """Safely evaluate simple expressions with limited scope."""
    ALLOWED_NODES = {
        ast.Expression, ast.Module, ast.Expr,
        ast.Constant, ast.Name, ast.Load,
        ast.UnaryOp, ast.UAdd, ast.USub, ast.Not,
        ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.In, ast.NotIn, ast.Is, ast.IsNot,
        ast.BoolOp, ast.And, ast.Or,
        ast.IfExp,
        ast.Subscript, ast.Index,
        ast.Slice,
        ast.List, ast.Tuple, ast.Dict, ast.Set,
        ast.Attribute,
        ast.Call,
        ast.keyword,
        ast.Starred,
    }

    def __init__(self, output: str, events: list[dict]):
        self._output = output
        self._events = events
        self._ns = {"output": output, "events": events, "str": str, "int": int, "float": float, "len": len, "bool": bool}

    def visit(self, node) -> object:
        if type(node) not in self.ALLOWED_NODES:
            raise ValueError(f"Expression uses unsupported construct: {type(node).__name__}")
        return super().visit(node)

    def visit_Expression(self, node) -> object:
        return self.visit(node.body)

    def visit_Constant(self, node) -> object:
        return node.value

    def visit_Name(self, node) -> object:
        if node.id in self._ns:
            return self._ns[node.id]
        raise NameError(f"Name '{node.id}' is not allowed")

    def visit_UnaryOp(self, node) -> object:
        val = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not val
        if isinstance(node.op, ast.UAdd):
            return +val
        if isinstance(node.op, ast.USub):
            return -val
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    def visit_BinOp(self, node) -> object:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

    def visit_BoolOp(self, node) -> object:
        if isinstance(node.op, ast.And):
            result = True
            for val in node.values:
                result = self.visit(val)
                if not result:
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for val in node.values:
                result = self.visit(val)
                if result:
                    return result
            return result
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def visit_Compare(self, node) -> bool:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(op, ast.Eq):
                if left != right:
                    return False
            elif isinstance(op, ast.NotEq):
                if left == right:
                    return False
            elif isinstance(op, ast.Lt):
                if not (left < right):
                    return False
            elif isinstance(op, ast.LtE):
                if not (left <= right):
                    return False
            elif isinstance(op, ast.Gt):
                if not (left > right):
                    return False
            elif isinstance(op, ast.GtE):
                if not (left >= right):
                    return False
            elif isinstance(op, ast.In):
                if left not in right:
                    return False
            elif isinstance(op, ast.NotIn):
                if left in right:
                    return False
            elif isinstance(op, ast.Is):
                if left is not right:
                    return False
            elif isinstance(op, ast.IsNot):
                if left is right:
                    return False
            else:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
            left = right
        return True

    def visit_IfExp(self, node) -> object:
        cond = self.visit(node.test)
        if cond:
            return self.visit(node.body)
        else:
            return self.visit(node.orelse)

    def visit_Subscript(self, node) -> object:
        value = self.visit(node.value)
        slice_val = self.visit(node.slice)
        return value[slice_val]

    def visit_Index(self, node) -> object:
        return self.visit(node.value)

    def visit_Slice(self, node) -> object:
        lower = self.visit(node.lower) if node.lower else None
        upper = self.visit(node.upper) if node.upper else None
        step = self.visit(node.step) if node.step else None
        return slice(lower, upper, step)

    def visit_List(self, node) -> list:
        return [self.visit(el) for el in node.elts]

    def visit_Tuple(self, node) -> tuple:
        return tuple(self.visit(el) for el in node.elts)

    def visit_Dict(self, node) -> dict:
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_Set(self, node) -> set:
        return {self.visit(el) for el in node.elts}

    def visit_Attribute(self, node) -> object:
        obj = self.visit(node.value)
        return getattr(obj, node.attr)

    def visit_Call(self, node) -> object:
        func = self.visit(node.func)
        args = [self.visit(a) for a in node.args]
        keywords = {kw.arg: self.visit(kw.value) for kw in node.keywords if kw.arg}
        return func(*args, **keywords)

    def visit_keyword(self, node) -> object:
        return self.visit(node.value)

    def visit_Starred(self, node) -> object:
        return self.visit(node.value)

def _check_custom(output: str, events: list[dict], expr: str) -> bool:
    """Evaluate a custom Python expression using a safe AST evaluator."""
    try:
        tree = ast.parse(expr, mode="eval")
        evaluator = _SafeExprEvaluator(output, events)
        result = evaluator.visit(tree)
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
