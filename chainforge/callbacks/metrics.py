"""Metrics callback — collects timing and usage metrics for agent runs."""

from __future__ import annotations

import datetime
import time
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from chainforge.callbacks.base import BaseCallback


class RunMetrics(BaseModel):
    """Collected metrics for a single agent run."""

    start_time: str = Field(default="")
    end_time: str | None = Field(default=None)
    duration_s: float = Field(default=0.0)
    llm_calls: int = Field(default=0)
    tool_calls: int = Field(default=0)
    total_tool_duration_s: float = Field(default=0.0)
    total_prompt_chars: int = Field(default=0)
    total_response_chars: int = Field(default=0)
    errors: int = Field(default=0)
    tool_details: dict[str, int] = Field(default_factory=dict)


class MetricsCallback(BaseCallback):
    """Collects timing and usage metrics during agent execution.

    Provides structured data for monitoring, profiling, and cost estimation.

    Usage:
        from chainforge.callbacks import MetricsCallback

        metrics = MetricsCallback()
        agent = Agent(llm=llm, callbacks=[metrics])

        stream = await agent.run("Hello")
        async for event in stream: ...

        report = metrics.get_report()
        print(f"Duration: {report['duration_s']}s")
        print(f"LLM calls: {report['llm_calls']}")
        print(f"Tool calls: {report['tool_calls']}")
    """

    name: str = "metrics"

    def __init__(self):
        self._metrics = RunMetrics()
        self._tool_timers: dict[str, float] = {}
        self._run_active = False

    async def on_agent_start(self, prompt: str, context: dict | None = None) -> None:
        self._metrics = RunMetrics(start_time=datetime.datetime.now(datetime.timezone.utc).isoformat())
        self._metrics.total_prompt_chars = len(prompt)
        self._run_active = True

    async def on_agent_end(self, output: str, context: dict | None = None) -> None:
        if self._run_active:
            self._metrics.end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._metrics.total_response_chars = len(output)
            self._metrics.duration_s = self._calc_duration()
            self._run_active = False

    async def on_llm_start(self, messages: list, context: dict | None = None) -> None:
        self._metrics.llm_calls += 1

    async def on_llm_end(self, response: Any, context: dict | None = None) -> None:
        content = getattr(response, "content", "") or ""
        self._metrics.total_response_chars += len(content)

    async def on_tool_start(self, tool_name: str, args: dict, context: dict | None = None) -> None:
        self._metrics.tool_calls += 1
        self._tool_timers[tool_name] = time.monotonic()
        self._metrics.tool_details[tool_name] = self._metrics.tool_details.get(tool_name, 0) + 1

    async def on_tool_end(self, tool_name: str, result: str, context: dict | None = None) -> None:
        start = self._tool_timers.pop(tool_name, None)
        if start is not None:
            duration = time.monotonic() - start
            self._metrics.total_tool_duration_s += duration

    async def on_error(self, error: Exception, context: dict | None = None) -> None:
        self._metrics.errors += 1

    def get_report(self) -> dict[str, Any]:
        """Get a metrics report as a dict."""
        return {
            "duration_s": round(self._metrics.duration_s, 3),
            "llm_calls": self._metrics.llm_calls,
            "tool_calls": self._metrics.tool_calls,
            "total_tool_duration_s": round(self._metrics.total_tool_duration_s, 3),
            "total_prompt_chars": self._metrics.total_prompt_chars,
            "total_response_chars": self._metrics.total_response_chars,
            "errors": self._metrics.errors,
            "tools_used": dict(self._metrics.tool_details),
            "start_time": self._metrics.start_time,
            "end_time": self._metrics.end_time or "",
        }

    def reset(self) -> None:
        """Reset metrics for a new run."""
        self._metrics = RunMetrics()
        self._tool_timers.clear()
        self._run_active = False

    def _calc_duration(self) -> float:
        if self._metrics.start_time and self._metrics.end_time:
            start = datetime.datetime.fromisoformat(self._metrics.start_time)
            end = datetime.datetime.fromisoformat(self._metrics.end_time)
            return (end - start).total_seconds()
        return 0.0
