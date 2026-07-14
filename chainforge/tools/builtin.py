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
"""Built-in utility tools.

WARNING: The calculate() tool previously used eval(), which was a security risk.
It now uses an AST-based safe math parser that only permits numeric expressions
and a restricted set of math functions.
"""

from __future__ import annotations

import ast
import datetime
import math as _math
import operator
from typing import Any

from chainforge.core.tool import tool


_SAFE_MATH_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": _math.sqrt,
    "pow": _math.pow,
    "sin": _math.sin,
    "cos": _math.cos,
    "tan": _math.tan,
    "log": _math.log,
    "log10": _math.log10,
    "exp": _math.exp,
    "ceil": _math.ceil,
    "floor": _math.floor,
    "pi": _math.pi,
    "e": _math.e,
    "inf": _math.inf,
    "nan": _math.nan,
}

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class _SafeMathVisitor(ast.NodeVisitor):
    """AST visitor that evaluates a math expression safely."""

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(self.visit(node.operand))

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_Call(self, node: ast.Call) -> Any:
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name is None or func_name not in _SAFE_MATH_FUNCS:
            raise ValueError(f"Unsupported function: {func_name!r}")
        args = [self.visit(arg) for arg in node.args]
        return _SAFE_MATH_FUNCS[func_name](*args)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in _SAFE_MATH_FUNCS:
            val = _SAFE_MATH_FUNCS[node.id]
            if not callable(val):
                return val
        raise ValueError(f"Unsupported name: {node.id!r}")

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")


def _safe_eval(expression: str) -> float:
    """Evaluate a mathematical expression safely using AST parsing.

    Only allows: numbers, +, -, *, /, //, %, **, parentheses, and a
    restricted set of math functions (sqrt, sin, cos, log, etc.).
    """
    tree = ast.parse(expression, mode="eval")
    return _SafeMathVisitor().visit(tree)


@tool
def current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Get the current date and time in the specified format."""
    return datetime.datetime.now().strftime(format)


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression. Use with caution."""
    try:
        result = _safe_eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def echo(text: str) -> str:
    """Return the input text as-is. Useful for testing."""
    return text


# ── Code Sandbox Tools ─────────────────────────────────────────────────────

_sandbox_instance = None


def _get_sandbox(timeout: int = 30):
    """Get or create a lazy subprocess sandbox."""
    global _sandbox_instance
    if _sandbox_instance is None:
        from chainforge.sandbox.subprocess import SubprocessSandbox
        _sandbox_instance = SubprocessSandbox(timeout=timeout)
    return _sandbox_instance


@tool
async def execute_python(code: str, timeout: int = 30) -> str:
    """Execute Python code in a sandboxed subprocess and return the output.

    Use this for data analysis, calculation, file processing, and any task
    that benefits from running actual code. The environment is isolated from
    the host system.

    Args:
        code: Python source code to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        stdout and stderr from the execution.
    """
    sandbox = _get_sandbox(timeout=timeout)
    result = await sandbox.execute(code, "python")
    output_parts = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(f"[STDERR]\n{result.stderr}")
    if result.exit_code != 0:
        output_parts.insert(0, f"[Exit code: {result.exit_code}]")
    return "\n".join(output_parts)


@tool
async def execute_bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command in a sandboxed subprocess and return the output.

    Use for file operations, system tasks, and running CLI tools.
    The environment is isolated from the host system.

    Args:
        command: Shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        stdout and stderr from the execution.
    """
    sandbox = _get_sandbox(timeout=timeout)
    result = await sandbox.execute(command, "bash")
    output_parts = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(f"[STDERR]\n{result.stderr}")
    if result.exit_code != 0:
        output_parts.insert(0, f"[Exit code: {result.exit_code}]")
    return "\n".join(output_parts)
