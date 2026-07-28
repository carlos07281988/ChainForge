# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""ExperienceRecorder — middleware that auto-records agent experiences."""
from __future__ import annotations
import time, uuid
from collections.abc import Callable
from chainforge.core.llm import LLMResponse
from chainforge.core.stream import StreamEvent
from chainforge.enterprise.collective.experience import Experience
from chainforge.enterprise.collective.memory import CollectiveMemory
from chainforge.logging import get_logger

logger = get_logger("enterprise.collective.recorder")

class ExperienceRecorder:
    """Middleware: auto-record agent execution as an Experience.

    Usage:
        cm = CollectiveMemory()
        agent = Agent(llm=llm, tools=[...], middlewares=[ExperienceRecorder(cm).middleware])
    """

    def __init__(self, memory: CollectiveMemory):
        self._memory = memory

    def middleware(self, task_hint: str = "") -> Callable:
        """Create a middleware that records an Experience after each run."""
        start = time.time()
        tokens_used = 0
        cost_total = 0.0
        model_used = "unknown"
        content_collected: list[str] = []

        async def _mw(messages, ctx, next_handler):
            nonlocal model_used, tokens_used, cost_total
            async for event in next_handler(messages, ctx):
                if isinstance(event, LLMResponse):
                    if event.usage:
                        tokens_used = event.usage.get("total_tokens", 0)
                    cost_total = event.cost or 0.0
                    model_used = event.model or "unknown"
                elif isinstance(event, StreamEvent) and event.type == "text":
                    if event.content:
                        content_collected.append(str(event.content)[:500])
                yield event

            # Record experience
            task_summary = task_hint or (content_collected[0][:100] if content_collected else "unknown")
            exp = Experience(
                id=uuid.uuid4().hex[:12],
                task=task_summary,
                task_type="general",
                tools_used=ctx.get("tool_names", []),
                model_used=model_used,
                outcome="success",
                cost=cost_total,
                tokens=tokens_used,
                duration_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )
            self._memory.add(exp)
            logger.debug(f"Experience recorded: {exp.id}")

        return _mw
