"""Performance Budget — declare and enforce execution budgets for agents.

Usage:
    from chainforge.middleware.budget import PerformanceContract, budget_middleware

    contract = PerformanceContract(
        max_cost_usd=0.10,
        max_llm_calls=5,
        max_tool_calls=10,
        max_latency_seconds=30,
    )
    agent = Agent(llm=llm, middlewares=[budget_middleware(contract)])
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


class PerformanceContract(BaseModel):
    """Declare performance limits for agent execution.

    The budget is enforced in real-time: if any limit is exceeded,
    a `budget_exceeded` event is emitted and execution stops.
    """

    max_cost_usd: float | None = Field(default=None, ge=0, description="Max estimated cost in USD")
    max_llm_calls: int | None = Field(default=None, ge=1, description="Max LLM generate() calls")
    max_tool_calls: int | None = Field(default=None, ge=1, description="Max tool executions")
    max_latency_seconds: float | None = Field(default=None, ge=0, description="Max wall-clock seconds")
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)


class BudgetTracker(BaseModel):
    """Tracks execution metrics against a PerformanceContract."""

    llm_calls: int = Field(default=0)
    tool_calls: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    start_time: float = Field(default_factory=time.time)
    tool_names: list[str] = Field(default_factory=list)
    exceeded: str | None = Field(default=None)
    exceeded_details: dict[str, Any] = Field(default_factory=dict)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def check(self, contract: PerformanceContract) -> bool:
        """Check if any budget limit is exceeded. Returns True if budget OK."""
        limits = [
            ("max_llm_calls", contract.max_llm_calls, self.llm_calls, "LLM calls exceeded"),
            ("max_tool_calls", contract.max_tool_calls, self.tool_calls, "Tool calls exceeded"),
            ("max_cost_usd", contract.max_cost_usd, self.total_cost, "Cost exceeded"),
            ("max_latency_seconds", contract.max_latency_seconds, self.elapsed, "Latency exceeded"),
        ]
        for name, limit, current, msg in limits:
            if limit is not None and current > limit:
                self.exceeded = name
                self.exceeded_details = {"limit": limit, "actual": current, "message": msg}
                return False
        return True


def budget_middleware(contract: PerformanceContract):
    """Create a middleware that enforces a PerformanceContract.

    Usage:
        contract = PerformanceContract(max_tool_calls=5)
        agent = Agent(llm=llm, middlewares=[budget_middleware(contract)])
    """
    tracker = BudgetTracker()

    async def _middleware(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        tracker.start_time = time.time()
        tracker.llm_calls = 0
        tracker.tool_calls = 0
        tracker.total_cost = 0.0
        tracker.tool_names = []
        tracker.exceeded = None

        yield StreamEvent(
            type=EventType.status,
            content="budget:start",
            data=contract.model_dump(),
        )

        async for event in next_handler(messages, ctx):
            # Track costs and usage
            if event.type == EventType.tool_call:
                tracker.tool_calls += 1
                tracker.tool_names.append(event.data.get("name", ""))
            if event.type == EventType.state and event.data.get("state") == "thinking":
                tracker.llm_calls += 1

            # Check budget
            if not tracker.check(contract):
                yield StreamEvent(
                    type=EventType.status,
                    content="budget:exceeded",
                    data=tracker.exceeded_details,
                )
                break

            yield event

        # Final summary
        yield StreamEvent(
            type=EventType.status,
            content="budget:summary",
            data={
                "llm_calls": tracker.llm_calls,
                "tool_calls": tracker.tool_calls,
                "elapsed": tracker.elapsed,
                "exceeded": tracker.exceeded,
            },
        )

    return _middleware


__all__ = ["PerformanceContract", "BudgetTracker", "budget_middleware"]
