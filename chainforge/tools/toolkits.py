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
"""Toolkits — groups of related tools for common tasks."""

from __future__ import annotations

from typing import Any

from chainforge.core.tool import Tool, tool
from chainforge.logging import get_logger

logger = get_logger("tools.toolkits")


class ToolKit:
    """A group of related tools.

    Usage:
        toolkit = ToolKit(name="math", tools=[add, multiply])
        agent = Agent(llm=llm, tools=toolkit.tools)
    """

    def __init__(self, name: str, tools: list, description: str = ""):
        self.name = name
        self._tools = list(tools)
        self.description = description

    @property
    def tools(self) -> list:
        return list(self._tools)

    def add_tool(self, t: Any) -> None:
        self._tools.append(t)


def calculator_toolkit() -> ToolKit:
    """Create a toolkit with calculation tools."""
    import math as _math

    @tool
    def add(a: float, b: float) -> str:
        """Add two numbers."""
        return str(a + b)

    @tool
    def multiply(a: float, b: float) -> str:
        """Multiply two numbers."""
        return str(a * b)

    @tool
    def sqrt(x: float) -> str:
        """Calculate square root."""
        return str(_math.sqrt(x))

    @tool
    def power(base: float, exp: float) -> str:
        """Calculate base raised to exponent."""
        return str(_math.pow(base, exp))

    return ToolKit(name="calculator", tools=[add, multiply, sqrt, power], description="Basic math operations")


def file_toolkit() -> ToolKit:
    """Create a toolkit with file operation tools."""
    import os
    from pathlib import Path

    @tool
    def read_file(path: str) -> str:
        """Read contents of a file."""
        try:
            return Path(path).read_text()
        except Exception as e:
            return f"Error: {e}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file."""
        try:
            Path(path).write_text(content)
            return f"Written to {path}"
        except Exception as e:
            return f"Error: {e}"

    @tool
    def list_files(directory: str = ".") -> str:
        """List files in a directory."""
        try:
            files = os.listdir(directory)
            return "\n".join(files)
        except Exception as e:
            return f"Error: {e}"

    return ToolKit(name="file", tools=[read_file, write_file, list_files], description="File read/write/list operations")


def web_toolkit() -> ToolKit:
    """Create a toolkit with web operation tools."""
    @tool
    def fetch_url(url: str) -> str:
        """Fetch a URL and return content."""
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read().decode()[:2000]
        except Exception as e:
            return f"Error: {e}"

    return ToolKit(name="web", tools=[fetch_url], description="Web fetch operations")
