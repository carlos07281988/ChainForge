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
"""CostTracker -- automatic LLM cost recording middleware."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from chainforge.core.llm import LLMResponse
from chainforge.enterprise.economics.ledger import CostRecord, TokenLedger
from chainforge.enterprise.economics.report import CostReport, CostOptimization
from chainforge.logging import get_logger

logger = get_logger("enterprise.economics")


class CostTracker:
    """Tracks LLM costs automatically via middleware.

    Usage:
        tracker = CostTracker(backend="sqlite", db_path="costs.db")

        agent = Agent(
            llm=SmartRouter(...),
            middlewares=[
                tracker.middleware(attribution={
                    "project": "customer-support",
                    "department": "operations",
                }),
            ],
        )

        # Query costs
        report = tracker.report(group_by="project", period="this-month")
    """

    def __init__(self, backend: str = "memory", db_path: str | None = None):
        self._ledger = TokenLedger(backend=backend, db_path=db_path)

    def middleware(
        self, attribution: dict[str, str] | None = None
    ) -> Callable:
        """Create an agent middleware that records costs.

        The middleware intercepts stream events and records costs from
        LLMResponse objects that carry usage data.

        Args:
            attribution: Labels for cost attribution
                         (project, department, tenant, etc.).
        """
        attr = attribution or {}

        async def _mw(messages, ctx, next_handler):
            start = time.time()
            provider = ctx.get("provider", "unknown")

            async for event in next_handler(messages, ctx):
                # LLMResponse carries usage + cost
                if isinstance(event, LLMResponse) and event.usage:
                    model_used = event.model or ctx.get("model", "unknown")
                    record = CostRecord(
                        timestamp=time.time(),
                        model=model_used,
                        provider=provider,
                        input_tokens=event.usage.get("prompt_tokens", 0),
                        output_tokens=event.usage.get("completion_tokens", 0),
                        cost=event.cost or 0.0,
                        duration_ms=(time.time() - start) * 1000,
                        attribution=dict(attr),
                    )
                    self._ledger.record(record)
                    logger.debug(
                        f"Cost recorded: ${record.cost:.6f} "
                        f"({record.model}, {record.input_tokens}+"
                        f"{record.output_tokens} tokens)"
                    )
                yield event

        return _mw

    def report(
        self,
        group_by: str = "model",
        period: str | tuple[str, str] | None = None,
    ) -> CostReport:
        """Generate a cost report.

        Args:
            group_by: model, provider, project, department, tenant.
            period: today, this-month, last-30-days, (start, end) tuple.

        Returns:
            CostReport with aggregated data.
        """
        rows = self._ledger.query(group_by=group_by, period=period)
        total = sum(r["total_cost"] for r in rows)
        return CostReport(
            total=total,
            rows=rows,
            group_by=group_by,
            period=str(period) if period else "all",
        )

    def optimize(self, period: str = "last-30-days") -> CostOptimization:
        """Analyze historical data and suggest cost optimizations.

        Args:
            period: Analysis period.

        Returns:
            CostOptimization with potential_savings and itemized suggestions.
        """
        rows = self._ledger.query(group_by="model", period=period)
        suggestions: list[str] = []
        potential_savings = 0.0

        for row in rows:
            model = row["dimension"]
            cost = row["total_cost"]
            calls = row["calls"]

            # Suggest downgrade for expensive models on simple calls
            if model in ("gpt-4o", "claude-opus-4", "gemini-2.0-pro"):
                if cost > 50.0 and calls > 100:
                    cheaper = {
                        "gpt-4o": "gpt-4o-mini",
                        "claude-opus-4": "claude-sonnet-4-20250514",
                        "gemini-2.0-pro": "gemini-2.0-flash",
                    }.get(model, "gpt-4o-mini")
                    save = cost * 0.5
                    potential_savings += save
                    suggestions.append(
                        f"Switch {calls} calls from {model} -> {cheaper}: "
                        f"save ~${save:.2f}"
                    )

        return CostOptimization(
            potential_savings=round(potential_savings, 2),
            items=suggestions,
        )

    def total_cost(
        self, period: str | tuple[str, str] | None = None
    ) -> float:
        """Get total spending for a period."""
        return self._ledger.total_cost(period)

    def close(self) -> None:
        self._ledger.close()
