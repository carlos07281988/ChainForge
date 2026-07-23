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
"""Tool & Agent Lifecycle Hooks — before/after hooks for tools and agents.

Inspired by Google ADK's before_tool/after_tool and lifecycle callback system.
Provides fine-grained hooks at the tool and agent level, more granular than
the existing Callback system (which is one-way observational).

Hooks can modify behavior (e.g., transform arguments, skip execution),
while Callbacks only observe.

Usage:
    @tool
    @before_tool(validate_input)
    def my_tool(x: str) -> str: ...

    agent = Agent(
        llm=llm,
        hooks=[logging_hook, metrics_hook],
    )
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import StreamEvent

# ── Hook protocol ──────────────────────────────────────────────────────────


class ToolHook:
    """Lifecycle hooks for a single tool execution.

    Subclass to implement custom before/after behavior.

    Usage:
        class MyToolHook(ToolHook):
            async def before_run(self, name: str, args: dict, ctx: dict) -> dict | None:
                log(f"Running {name} with {args}")
                return args  # modified args, or None to skip

            async def after_run(self, name: str, args: dict, result: Any, ctx: dict) -> Any:
                log(f"Result: {result}")
                return result  # modified result
    """

    async def before_run(self, name: str, args: dict[str, Any],
                         ctx: dict[str, Any]) -> dict[str, Any] | None:
        """Called before each tool execution.

        Args:
            name: Tool name.
            args: Tool arguments (may be modified).
            ctx: Execution context dict.

        Returns:
            Modified args dict, or None to skip tool execution entirely.
        """
        return args

    async def after_run(self, name: str, args: dict[str, Any],
                        result: Any, ctx: dict[str, Any]) -> Any:
        """Called after each successful tool execution.

        Args:
            name: Tool name.
            args: Original tool arguments.
            result: Tool result (may be modified).
            ctx: Execution context dict.

        Returns:
            Modified result.
        """
        return result

    async def on_error(self, name: str, args: dict[str, Any],
                       error: Exception, ctx: dict[str, Any]) -> None:
        """Called when a tool execution raises an exception."""
        pass


class AgentHook:
    """Lifecycle hooks for Agent execution.

    Subclass to hook into agent-level events.

    Usage:
        class MyAgentHook(AgentHook):
            async def on_start(self, prompt: str, ctx: dict):
                print(f"Agent starting with: {prompt[:50]}...")

            async def on_step(self, event: StreamEvent, ctx: dict):
                if event.type == "tool_call":
                    print(f"Tool call: {event.data.get('name')}")
    """

    async def on_start(self, prompt: str | list[Message],
                       ctx: dict[str, Any]) -> None:
        """Called when the agent begins processing."""

    async def on_step(self, event: StreamEvent,
                      ctx: dict[str, Any]) -> StreamEvent | None:
        """Called for each stream event during execution.

        Return None to suppress the event, or return a modified event.
        """
        return event

    async def on_error(self, error: Exception,
                       ctx: dict[str, Any]) -> None:
        """Called when the agent encounters an error."""

    async def on_finish(self, final_content: str | None,
                        ctx: dict[str, Any]) -> None:
        """Called when the agent finishes execution."""


# ── Hook registry ─────────────────────────────────────────────────────────


class _HookChain:
    """Chain multiple hooks together and execute them in order."""

    def __init__(self, hooks: list):
        self._hooks = list(hooks)

    async def run_before_tool(self, name: str, args: dict[str, Any],
                               ctx: dict[str, Any]) -> dict[str, Any] | None:
        """Run all before_tool hooks in order."""
        current_args = dict(args)
        for hook in self._hooks:
            if isinstance(hook, ToolHook):
                result = await hook.before_run(name, current_args, ctx)
                if result is None:
                    return None  # Skip execution
                current_args = result
        return current_args

    async def run_after_tool(self, name: str, args: dict[str, Any],
                              result: Any, ctx: dict[str, Any]) -> Any:
        """Run all after_tool hooks in order."""
        current_result = result
        for hook in self._hooks:
            if isinstance(hook, ToolHook):
                current_result = await hook.after_run(name, args, current_result, ctx)
        return current_result

    async def run_tool_error(self, name: str, args: dict[str, Any],
                              error: Exception, ctx: dict[str, Any]) -> None:
        for hook in self._hooks:
            if isinstance(hook, ToolHook):
                await hook.on_error(name, args, error, ctx)

    async def run_agent_start(self, prompt: str | list[Message],
                               ctx: dict[str, Any]) -> None:
        for hook in self._hooks:
            if isinstance(hook, AgentHook):
                await hook.on_start(prompt, ctx)

    async def run_agent_step(self, event: StreamEvent,
                              ctx: dict[str, Any]) -> StreamEvent | None:
        for hook in self._hooks:
            if isinstance(hook, AgentHook):
                result = await hook.on_step(event, ctx)
                if result is None:
                    return None
                event = result
        return event

    async def run_agent_error(self, error: Exception,
                               ctx: dict[str, Any]) -> None:
        for hook in self._hooks:
            if isinstance(hook, AgentHook):
                await hook.on_error(error, ctx)

    async def run_agent_finish(self, final_content: str | None,
                                ctx: dict[str, Any]) -> None:
        for hook in self._hooks:
            if isinstance(hook, AgentHook):
                await hook.on_finish(final_content, ctx)


# ── Decorator-based tool hooks ───────────────────────────────────────────


class _BeforeToolDecorator:
    """Decorator that attaches before/after hooks to a tool."""

    def __init__(self, fn: Callable):
        self._fn = fn
        self._before_hooks: list[Callable] = []
        self._after_hooks: list[Callable] = []

    def before(self, hook_fn: Callable) -> "_BeforeToolDecorator":
        """Register a before-tool hook.

        The hook receives (name, args, ctx) and must return args or None.
        """
        self._before_hooks.append(hook_fn)
        return self

    def after(self, hook_fn: Callable) -> "_BeforeToolDecorator":
        """Register an after-tool hook.

        The hook receives (name, args, result, ctx) and must return result.
        """
        self._after_hooks.append(hook_fn)
        return self

    async def __call__(self, name: str, args: dict[str, Any],
                        ctx: dict[str, Any]) -> Any:
        current_args = dict(args)
        for hook in self._before_hooks:
            result = hook(name, current_args, ctx)
            if hasattr(result, "__await__"):
                result = await result
            if result is None:
                return None
            current_args = result

        result = self._fn(**current_args)
        if hasattr(result, "__await__"):
            result = await result

        for hook in self._after_hooks:
            result = hook(name, current_args, result, ctx)
            if hasattr(result, "__await__"):
                result = await result
        return result


def before_tool(fn: Callable | None = None, *,
                before: Callable | None = None,
                after: Callable | None = None) -> Callable:
    """Decorator to add before/after hooks to a tool function.

    Usage:
        @tool
        @before_tool
        def my_tool(x: str) -> str:
            return f"Hello {x}"

        @my_tool.before
        def validate(name, args, ctx):
            assert "x" in args, "Missing x"
            return args
    """
    if fn is not None:
        return _BeforeToolDecorator(fn)
    return _BeforeToolDecorator


# ── Concrete hook implementations ─────────────────────────────────────────


class LoggingHook(ToolHook, AgentHook):
    """Hook that logs tool and agent lifecycle events."""

    def __init__(self, name: str = "hooks"):
        self.name = name

    async def before_run(self, name: str, args: dict[str, Any],
                         ctx: dict[str, Any]) -> dict[str, Any] | None:
        from chainforge.logging import get_logger
        get_logger(self.name).debug(f"Tool starting: {name}({args})")
        return args

    async def after_run(self, name: str, args: dict[str, Any],
                        result: Any, ctx: dict[str, Any]) -> Any:
        from chainforge.logging import get_logger
        get_logger(self.name).debug(f"Tool done: {name} -> {str(result)[:100]}")
        return result

    async def on_start(self, prompt: str | list[Message],
                       ctx: dict[str, Any]) -> None:
        from chainforge.logging import get_logger
        if isinstance(prompt, str):
            get_logger(self.name).info(f"Agent started: len={len(prompt)}")
        else:
            get_logger(self.name).info(f"Agent started: messages={len(prompt)}")

    async def on_finish(self, final_content: str | None,
                        ctx: dict[str, Any]) -> None:
        from chainforge.logging import get_logger
        get_logger(self.name).info(f"Agent finished: len={len(final_content or '')}")


class MetricsHook(AgentHook):
    """Hook that collects execution timing and event counts."""

    def __init__(self):
        self.start_time: float = 0.0
        self.event_counts: dict[str, int] = {}
        self.tool_calls: list[dict] = []
        self.errors: list[str] = []

    async def on_start(self, prompt: str | list[Message],
                       ctx: dict[str, Any]) -> None:
        self.start_time = time.time()
        self.event_counts.clear()
        self.tool_calls.clear()
        self.errors.clear()

    async def on_step(self, event: StreamEvent,
                      ctx: dict[str, Any]) -> StreamEvent | None:
        t = event.type.value if hasattr(event.type, 'value') else str(event.type)
        self.event_counts[t] = self.event_counts.get(t, 0) + 1
        if event.type == "tool_call":
            self.tool_calls.append({
                "name": event.data.get("name", ""),
                "args": event.data.get("args", {}),
            })
        if event.type == "error":
            self.errors.append(event.content or str(event.data))
        return event

    async def on_finish(self, final_content: str | None,
                        ctx: dict[str, Any]) -> None:
        elapsed = time.time() - self.start_time

    def report(self) -> dict[str, Any]:
        return {
            "duration_seconds": time.time() - self.start_time if self.start_time else 0,
            "event_counts": dict(self.event_counts),
            "tool_calls": len(self.tool_calls),
            "errors": len(self.errors),
        }


class TimingHook(ToolHook):
    """Hook that measures and logs tool execution time."""

    def __init__(self, threshold_ms: float = 1000.0):
        self.threshold_ms = threshold_ms
        self.timings: dict[str, list[float]] = {}

    async def before_run(self, name: str, args: dict[str, Any],
                         ctx: dict[str, Any]) -> dict[str, Any] | None:
        ctx["_hook_timing_start"] = time.time()
        return args

    async def after_run(self, name: str, args: dict[str, Any],
                        result: Any, ctx: dict[str, Any]) -> Any:
        start = ctx.pop("_hook_timing_start", None)
        if start is not None:
            elapsed_ms = (time.time() - start) * 1000
            self.timings.setdefault(name, []).append(elapsed_ms)
            if elapsed_ms > self.threshold_ms:
                from chainforge.logging import get_logger
                get_logger("hooks.timing").warning(
                    f"Slow tool: {name} took {elapsed_ms:.1f}ms"
                )
        return result

    def stats(self) -> dict[str, dict[str, float]]:
        stats: dict[str, dict[str, float]] = {}
        for name, times in self.timings.items():
            stats[name] = {
                "count": len(times),
                "avg_ms": sum(times) / len(times),
                "max_ms": max(times),
                "min_ms": min(times),
            }
        return stats
