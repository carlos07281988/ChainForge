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
"""In-memory credit ledger for cross-agent transactions.

Tracks every billing event, supports querying by agent / period,
and provides settlement operations.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from chainforge.enterprise.economy.contract import Transaction


def _parse_period(period: str | tuple[str, str] | None) -> tuple[float, float] | None:
    """Convert a human-readable period into a (start_ts, end_ts) float pair.

    Supported string aliases:
    - ``"today"`` — midnight UTC today through now
    - ``"this-month"`` — first day of current month through now
    - ``"last-30-days"`` — 30 days ago through now

    A tuple of two ISO-8601 date strings is also accepted and converted
    to Unix timestamps.  Returns ``None`` when *period* is ``None``
    (meaning "all time").
    """
    if period is None:
        return None

    now_ts = time.time()
    now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)

    if isinstance(period, tuple):
        start = datetime.fromisoformat(period[0]).timestamp()
        end = datetime.fromisoformat(period[1]).timestamp()
        return (start, end)

    period_lower = period.lower()

    if period_lower == "today":
        start = datetime(now_dt.year, now_dt.month, now_dt.day, tzinfo=timezone.utc)
        return (start.timestamp(), now_ts)

    if period_lower == "this-month":
        start = datetime(now_dt.year, now_dt.month, 1, tzinfo=timezone.utc)
        return (start.timestamp(), now_ts)

    if period_lower == "last-30-days":
        return (now_ts - 30 * 86400, now_ts)

    # Fallback: try parsing as ISO date range "YYYY-MM-DD/YYYY-MM-DD"
    if "/" in period_lower:
        parts = period_lower.split("/", 1)
        start = datetime.fromisoformat(parts[0].strip()).timestamp()
        end = datetime.fromisoformat(parts[1].strip()).timestamp()
        return (start, end)

    raise ValueError(
        f"Unsupported period {period!r}. "
        f"Use 'today', 'this-month', 'last-30-days', "
        f"a tuple of ISO dates, or 'YYYY-MM-DD/YYYY-MM-DD'."
    )


class CreditLedger:
    """In-memory double-entry-style ledger for cross-agent tool-call billing.

    Each :class:`Transaction` records a debit (sender owes) / credit
    (receiver earns) pair.  The ledger supports time-range queries and
    bulk settlement.
    """

    def __init__(self) -> None:
        self._transactions: list[Transaction] = []

    # ---- recording ---------------------------------------------------------

    def record(self, tx: Transaction) -> None:
        """Append a transaction to the ledger."""
        self._transactions.append(tx)

    # ---- balances ----------------------------------------------------------

    def balance(self, agent_id: str) -> float:
        """Net balance for *agent_id* (received minus sent, unsettled only).

        Positive = the agent is a net creditor; negative = net debtor.
        """
        received = sum(
            tx.total_amount
            for tx in self._transactions
            if tx.to_agent_id == agent_id and not tx.settled
        )
        sent = sum(
            tx.total_amount
            for tx in self._transactions
            if tx.from_agent_id == agent_id and not tx.settled
        )
        return received - sent

    # ---- queries -----------------------------------------------------------

    def outstanding(self, agent_id: str) -> list[Transaction]:
        """Return every *unsettled* transaction that involves *agent_id*."""
        return [
            tx
            for tx in self._transactions
            if not tx.settled
            and (tx.from_agent_id == agent_id or tx.to_agent_id == agent_id)
        ]

    def settle(self, tx_ids: list[str]) -> list[Transaction]:
        """Mark the given transaction IDs as settled and return them."""
        id_set = set(tx_ids)
        settled: list[Transaction] = []
        for tx in self._transactions:
            if tx.id in id_set and not tx.settled:
                tx.settled = True
                settled.append(tx)
        return settled

    def query(
        self, agent_id: str, period: str | tuple[str, str] | None = None
    ) -> list[Transaction]:
        """Return every transaction for *agent_id*, optionally filtered by period.

        *period* is forwarded to :func:`_parse_period`.
        """
        window = _parse_period(period)
        results: list[Transaction] = []
        for tx in self._transactions:
            if tx.from_agent_id != agent_id and tx.to_agent_id != agent_id:
                continue
            if window is not None:
                start, end = window
                if tx.timestamp < start or tx.timestamp > end:
                    continue
            results.append(tx)
        return results

    def all_transactions(self) -> list[Transaction]:
        """Return every transaction ever recorded."""
        return list(self._transactions)
