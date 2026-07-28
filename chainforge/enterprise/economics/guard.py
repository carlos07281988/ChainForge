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
"""BudgetGuard -- middleware that enforces daily spending limits."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.enterprise.economics.tracker import CostTracker
from chainforge.logging import get_logger

logger = get_logger("enterprise.economics.guard")


class BudgetGuard:
    """Middleware: enforce daily budget limits.

    On reaching the limit, can downgrade the model, block the request,
    or just warn and continue.

    Usage:
        guard = BudgetGuard(
            daily_limit=50.0,
            on_limit="downgrade",
            fallback_model="gpt-4o-mini",
            tracker=tracker,
        )

        agent = Agent(llm=SmartRouter(...), middlewares=[guard])
    """

    def __init__(
        self,
        daily_limit: float = 50.0,
        on_limit: str = "downgrade",
        fallback_model: str | None = None,
        tracker: CostTracker | None = None,
    ):
        self._daily_limit = daily_limit
        self._on_limit = on_limit  # downgrade | block | warn
        self._fallback_model = fallback_model
        self._tracker = tracker

    @property
    def daily_limit(self) -> float:
        return self._daily_limit

    async def __call__(
        self,
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        # Check budget
        today_spend = 0.0
        if self._tracker:
            today_spend = self._tracker.total_cost(period="today")

        if today_spend >= self._daily_limit:
            logger.warning(
                f"Daily budget ${self._daily_limit} exceeded "
                f"(spent: ${today_spend:.2f})"
            )

            if self._on_limit == "downgrade" and self._fallback_model:
                ctx["llm_override"] = self._fallback_model
                logger.info(f"BudgetGuard: downgrading to {self._fallback_model}")
            elif self._on_limit == "block":
                yield StreamEvent(
                    type=EventType.error,
                    content=(
                        f"Daily budget ${self._daily_limit:.2f} exceeded "
                        f"(spent: ${today_spend:.2f})"
                    ),
                    metadata={"reason": "budget_exceeded"},
                )
                return
            # "warn": just log and let through

        async for event in next_handler(messages, ctx):
            yield event
