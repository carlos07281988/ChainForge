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
"""Justice Guard — middleware that auto-collects evidence for every agent run."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.llm import LLMResponse
from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.enterprise.justice.evidence import EvidenceItem, EvidencePack
from chainforge.logging import get_logger

logger = get_logger("enterprise.justice")


class JusticeGuard:
    """Middleware: auto-collect evidence for every agent run.

    Creates a complete EvidencePack on each agent execution so that
    any decision can be reviewed, explained, or contested later.

    Usage::

        agent = Agent(
            llm=llm,
            tools=[...],
            middlewares=[JusticeGuard(evidence_ttl_days=365)],
        )
    """

    def __init__(self, evidence_ttl_days: int = 365, auto_generate_review: bool = True):
        self._evidence_ttl = evidence_ttl_days
        self._auto_review = auto_generate_review
        self._store: dict[str, EvidencePack] = {}

    async def __call__(
        self,
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        pack = EvidencePack(
            run_id=ctx.get("run_id", ""),
            agent_name=ctx.get("agent_name", "unknown"),
            tools_available=[t.name for t in ctx.get("tools", [])],
        )
        start = time.time()
        step = 0
        async for event in next_handler(messages, ctx):
            item = None
            if event.type == EventType.text:
                item = EvidenceItem(
                    step=step,
                    event_type="llm_call" if step == 0 else "llm_response",
                    content=str(event.data.get("content", ""))[:500],
                )
            elif event.type == EventType.tool_call:
                item = EvidenceItem(
                    step=step,
                    event_type="tool_call",
                    tool_name=str(event.data.get("tool_name", "")),
                    tool_args=event.data.get("arguments", {}),
                )
            elif event.type == EventType.tool_result:
                item = EvidenceItem(
                    step=step,
                    event_type="tool_result",
                    tool_name=str(event.data.get("tool_name", "")),
                    tool_result=str(event.data.get("result", ""))[:500],
                )
            elif isinstance(event, LLMResponse):
                item = EvidenceItem(
                    step=step,
                    event_type="llm_response",
                    content=str(event.content or "")[:500],
                    model=event.model,
                    tokens_used=event.usage.get("total_tokens", 0) if event.usage else 0,
                    cost=event.cost or 0.0,
                )
            if item:
                pack.items.append(item)
                step += 1
                pack.total_steps = step
            yield event
        pack.duration_ms = (time.time() - start) * 1000
        pack.total_tokens = sum(i.tokens_used for i in pack.items)
        pack.total_cost = sum(i.cost for i in pack.items)
        if pack.run_id:
            self._store[pack.run_id] = pack
        logger.info(f"EvidencePack recorded: {pack.run_id} ({pack.total_steps} steps)")

    def get_evidence(self, run_id: str) -> EvidencePack | None:
        return self._store.get(run_id)

    def all_evidence(self) -> list[EvidencePack]:
        return list(self._store.values())
