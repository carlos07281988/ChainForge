"""Built-in utility tools."""

from __future__ import annotations

import datetime

from chainforge.core.tool import tool


@tool
def current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Get the current date and time in the specified format."""
    return datetime.datetime.now().strftime(format)


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression. Use with caution."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def echo(text: str) -> str:
    """Return the input text as-is. Useful for testing."""
    return text
