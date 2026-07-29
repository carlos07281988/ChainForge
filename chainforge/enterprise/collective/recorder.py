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
"""ExperienceRecorder — middleware that auto-records agent experiences."""
from __future__ import annotations
import time, uuid
from collections.abc import Callable
from chainforge.core.llm import LLMResponse
from chainforge.core.stream import EventType, StreamEvent
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

    def middleware(self, task_hint: str = "", task_type: str = "general") -> Callable:
        """Create a middleware that records an Experience after each run."""

        async def _mw(messages, ctx, next_handler):
            start = time.time()
            tokens_used = 0
            cost_total = 0.0
            model_used = "unknown"
            content_collected: list[str] = []
            # Determine outcome from stream events
            outcome = "success"
            error_seen = False
            async for event in next_handler(messages, ctx):
                if isinstance(event, StreamEvent) and event.type == EventType.error:
                    error_seen = True
                if isinstance(event, LLMResponse):
                    if event.usage:
                        tokens_used = event.usage.get("total_tokens", 0)
                    cost_total = event.cost or 0.0
                    model_used = event.model or "unknown"
                elif isinstance(event, StreamEvent) and event.type == EventType.text:
                    if event.content:
                        content_collected.append(str(event.content)[:500])
                yield event

            # Record experience
            task_summary = task_hint or (content_collected[0][:100] if content_collected else "unknown")
            exp = Experience(
                id=uuid.uuid4().hex[:12],
                task=task_summary,
                task_type=task_type,
                tools_used=ctx.get("tool_names", []),
                model_used=model_used,
                outcome="failure" if error_seen else "success",
                cost=cost_total,
                tokens=tokens_used,
                duration_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )
            self._memory.add(exp)
            logger.debug(f"Experience recorded: {exp.id}")

        return _mw
