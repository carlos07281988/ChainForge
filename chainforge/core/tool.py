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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, or in the current law.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tool primitives — define and execute tools with type-safe schemas.

Provides:
  - Tool protocol: interface for any callable tool
  - ToolSpec: JSON Schema description
  - BaseTool: optional base class with _run / _arun lifecycle
  - FunctionTool: tool from a plain Python function
  - @tool decorator: auto-generates schema from type hints
  - Structured artifacts: tools can return non-string values
"""

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
    response_schema: dict[str, Any] | None = Field(default=None, description="JSON Schema of the return value")


@runtime_checkable
class Tool(Protocol):
    """Protocol for any callable tool."""

    @property
    def spec(self) -> ToolSpec:
        """Return the tool's JSON schema specification."""
        ...

    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool with given kwargs and return a result (str or structured)."""
        ...

    def __call__(self, **kwargs: Any) -> Any:
        """Synchronous execute."""
        ...


# ── BaseTool ─────────────────────────────────────────────────────────────


class BaseTool:
    """Optional base class for tools with lifecycle methods.

    Subclass and override _run() / _arun() for actual logic.
    Lifecycle hooks: on_start, on_end, on_error.

    Usage:
        class MyTool(BaseTool):
            def _run(self, x: int, y: int = 0) -> str:
                return f"Result: {x + y}"
    """

    name: str = ""
    description: str = ""

    def __init__(self):
        self._spec = self._build_spec()

    def _build_spec(self) -> ToolSpec:
        sig = inspect.signature(self._run)
        hints = get_type_hints(self._run)
        props: dict[str, Any] = {}
        required: list[str] = []

        for pname, param in sig.parameters.items():
            if pname == "return":
                continue
            if param.default is inspect.Parameter.empty:
                required.append(pname)
            props[pname] = FunctionTool._type_to_json_schema(hints.get(pname, str))

        return_type = hints.get("return")
        response_schema = None
        if return_type and hasattr(return_type, "model_json_schema"):
            try:
                response_schema = return_type.model_json_schema()
            except Exception:
                pass

        return ToolSpec(
            name=self.name or self.__class__.__name__.lower(),
            description=self.description or (self._run.__doc__ or "").strip(),
            parameters={"type": "object", "properties": props, "required": required},
            response_schema=response_schema,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def _run(self, **kwargs: Any) -> Any:
        """Override with synchronous tool logic."""
        raise NotImplementedError

    async def _arun(self, **kwargs: Any) -> Any:
        """Override with async tool logic. Falls back to _run()."""
        return self._run(**kwargs)

    async def on_start(self, **kwargs) -> None:
        """Lifecycle hook: called before tool execution."""

    async def on_end(self, result: Any) -> None:
        """Lifecycle hook: called after successful tool execution."""

    async def on_error(self, error: Exception) -> None:
        """Lifecycle hook: called on tool execution error."""

    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool with lifecycle hooks."""
        await self.on_start(**kwargs)
        try:
            if inspect.iscoroutinefunction(self._arun):
                result = await self._arun(**kwargs)
            else:
                result = self._run(**kwargs)
            await self.on_end(result)
            return result
        except Exception as e:
            await self.on_error(e)
            raise

    def __call__(self, **kwargs: Any) -> Any:
        from chainforge.core.utils import run_sync
        return run_sync(self.run(**kwargs))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.spec.name!r})"


# ── FunctionTool ─────────────────────────────────────────────────────────


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

        # Build response_schema from return type hint
        return_type = hints.get("return")
        response_schema = None
        if return_type and hasattr(return_type, "model_json_schema"):
            try:
                response_schema = return_type.model_json_schema()
            except Exception:
                pass
        elif return_type and return_type not in (str, int, float, bool, list, dict, Any):
            # Try Pydantic schema
            try:
                if hasattr(return_type, "schema"):
                    response_schema = return_type.schema()
            except Exception:
                pass

        return ToolSpec(
            name=self._name,
            description=self._description,
            parameters={"type": "object", "properties": props, "required": required},
            response_schema=response_schema,
        )

    @staticmethod
    def _type_to_json_schema(tp: type) -> dict:
        mapping = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
        }
        origin = getattr(tp, "__origin__", None)
        if origin is list:
            item_type = getattr(tp, "__args__", (str,))[0]
            return {"type": "array", "items": mapping.get(item_type, {"type": "string"})}
        if origin is dict:
            return {"type": "object"}
        # If it's a Pydantic model, get its schema
        if hasattr(tp, "model_json_schema"):
            try:
                return tp.model_json_schema()
            except Exception:
                pass
        return mapping.get(tp, {"type": "string"})

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool, returning str or structured data."""
        if self._is_async:
            result = await self._fn(**kwargs)
        else:
            result = self._fn(**kwargs)
        # Keep as-is (non-string) for structured artifacts,
        # but the Agent._execute_tool will str() it for messages.
        return result

    def __call__(self, **kwargs: Any) -> Any:
        from chainforge.core.utils import run_sync
        return run_sync(self.run(**kwargs))

    def __repr__(self) -> str:
        return f"FunctionTool(name={self._name!r})"


# ── @tool decorator ──────────────────────────────────────────────────────


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

    if fn is not None:
        return _wrap(fn)
    return _wrap
