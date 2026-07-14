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
"""Tool primitives — define and execute tools with type-safe schemas."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel, Field
from typing_extensions import Protocol, runtime_checkable


class ToolSpec(BaseModel):
    """JSON Schema description of a tool, matching OpenAI/Anthropic format."""

    name: str = Field(description="Tool name")
    description: str = Field(default="", description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})


@runtime_checkable
class Tool(Protocol):
    """Protocol for any callable tool."""

    @property
    def spec(self) -> ToolSpec:
        """Return the tool's JSON schema specification."""
        ...

    async def run(self, **kwargs: Any) -> str:
        """Execute the tool with given kwargs and return a string result."""
        ...

    def __call__(self, **kwargs: Any) -> str:
        """Synchronous execute (default: delegates to run via event loop)."""
        ...


class FunctionTool:
    """A tool built from a plain Python function."""

    def __init__(self, fn: Callable, name: str | None = None, description: str | None = None):
        self._fn = fn
        self._is_async = inspect.iscoroutinefunction(fn)
        self._name = name or fn.__name__
        self._description = description or (fn.__doc__ or "").strip()
        self._spec = self._build_spec()

    def _build_spec(self) -> ToolSpec:
        sig = inspect.signature(self._fn)
        hints = get_type_hints(self._fn)
        props: dict[str, Any] = {}
        required: list[str] = []

        for pname, param in sig.parameters.items():
            if pname == "return":
                continue
            if param.default is inspect.Parameter.empty:
                required.append(pname)
            json_type = self._type_to_json_schema(hints.get(pname, str))
            props[pname] = json_type

        return ToolSpec(
            name=self._name,
            description=self._description,
            parameters={"type": "object", "properties": props, "required": required},
        )

    @staticmethod
    def _type_to_json_schema(tp: type) -> dict:
        mapping = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
        }
        # Handle Optional / Union
        origin = getattr(tp, "__origin__", None)
        if origin is list:
            item_type = getattr(tp, "__args__", (str,))[0]
            return {"type": "array", "items": mapping.get(item_type, {"type": "string"})}
        if origin is dict:
            return {"type": "object"}
        return mapping.get(tp, {"type": "string"})

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, **kwargs: Any) -> str:
        if self._is_async:
            result = await self._fn(**kwargs)
        else:
            result = self._fn(**kwargs)
        return str(result)

    def __call__(self, **kwargs: Any) -> str:
        from chainforge.core.utils import run_sync
        return run_sync(self.run(**kwargs))

    def __repr__(self) -> str:
        return f"FunctionTool(name={self._name!r})"


def tool(fn: Callable | None = None, *, name: str | None = None, description: str | None = None) -> Callable | FunctionTool:
    """Decorator that wraps a function into a FunctionTool.

    Usage:
        @tool
        def my_func(x: str) -> str: ...

        @tool(name="custom_name", description="Does X")
        def my_func(x: str) -> str: ...
    """
    def _wrap(f: Callable) -> FunctionTool:
        return FunctionTool(f, name=name, description=description)

    # Called as @tool (no parens) → fn is the decorated function
    if fn is not None:
        return _wrap(fn)
    # Called as @tool(...) with args → fn is None, return wrapper
    return _wrap
