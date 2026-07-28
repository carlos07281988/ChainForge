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
"""AgentEconomy — top-level coordinator for cross-agent billing and settlement."""

from __future__ import annotations

from collections import defaultdict

from chainforge.enterprise.economy.contract import BillingContract, Transaction
from chainforge.enterprise.economy.invoice import Invoice, RevenueReport
from chainforge.enterprise.economy.ledger import CreditLedger


class AgentEconomy:
    """Orchestrates cross-agent billing, invoicing, and settlement.

    Manages a :class:`CreditLedger` and a registry of per-seller
    :class:`BillingContract` instances.  All methods are synchronous
    (in-memory, no I/O).
    """

    def __init__(self, settlement_currency: str = "usd") -> None:
        self.settlement_currency = settlement_currency
        self._ledger = CreditLedger()
        self._contracts: dict[str, BillingContract] = {}

    # ---- contract registry -------------------------------------------------

    def register_contract(self, agent_id: str, contract: BillingContract) -> None:
        """Store (or replace) the pricing contract for *agent_id* (the seller)."""
        self._contracts[agent_id] = contract

    def get_contract(self, agent_id: str) -> BillingContract | None:
        """Return the registered contract for *agent_id*, or ``None``."""
        return self._contracts.get(agent_id)

    # ---- invoicing ---------------------------------------------------------

    def invoice(self, agent_id: str, period: str | tuple[str, str] | None = None) -> Invoice:
        """Build a bill for *agent_id* (the buyer).

        Groups outgoing transactions by ``(to_agent_id, tool_name)``.
        """
        txs = self._ledger.query(agent_id, period=period)
        outgoing = [tx for tx in txs if tx.from_agent_id == agent_id]

        # Group by (to_agent, tool_name)
        groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
        for tx in outgoing:
            groups[(tx.to_agent_id, tx.tool_name)].append(tx)

        items: list[dict] = []
        total = 0.0
        for (seller, tool), group in groups.items():
            subtotal = sum(g.total_amount for g in group)
            items.append({
                "to_agent_id": seller,
                "tool_name": tool,
                "count": len(group),
                "subtotal": subtotal,
            })
            total += subtotal

        return Invoice(
            agent_id=agent_id,
            period=period or "all",
            items=items,
            total_payable=total,
        )

    def revenue(self, agent_id: str, period: str | tuple[str, str] | None = None) -> RevenueReport:
        """Build a revenue report for *agent_id* (the seller).

        Splits incoming transactions into settled vs. outstanding.
        """
        txs = self._ledger.query(agent_id, period=period)
        incoming = [tx for tx in txs if tx.to_agent_id == agent_id]

        total_earned = sum(tx.total_amount for tx in incoming)
        total_settled = sum(tx.total_amount for tx in incoming if tx.settled)
        total_outstanding = sum(tx.total_amount for tx in incoming if not tx.settled)

        # Group by (from_agent, tool_name)
        groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
        for tx in incoming:
            groups[(tx.from_agent_id, tx.tool_name)].append(tx)

        items: list[dict] = []
        for (buyer, tool), group in groups.items():
            subtotal = sum(g.total_amount for g in group)
            settled = sum(g.total_amount for g in group if g.settled)
            items.append({
                "from_agent_id": buyer,
                "tool_name": tool,
                "count": len(group),
                "subtotal": subtotal,
                "settled": settled,
            })

        return RevenueReport(
            agent_id=agent_id,
            period=period or "all",
            items=items,
            total_earned=total_earned,
            total_settled=total_settled,
            total_outstanding=total_outstanding,
        )

    # ---- settlement --------------------------------------------------------

    def settle(
        self,
        from_agent_id: str,
        to_agent_id: str,
        amount: float,
        method: str = "internal",
    ) -> list[Transaction]:
        """Settle outstanding transactions between *from_agent_id* and *to_agent_id*.

        Finds unsettled transactions from *from_agent_id* to *to_agent_id*
        and marks them as settled until *amount* is fully covered.
        Returns the list of transactions that were settled.
        """
        candidates = [
            tx
            for tx in self._ledger._transactions
            if tx.from_agent_id == from_agent_id
            and tx.to_agent_id == to_agent_id
            and not tx.settled
        ]
        # Sort oldest-first for FIFO settlement
        candidates.sort(key=lambda tx: tx.timestamp)

        remaining = amount
        settled_ids: list[str] = []
        for tx in candidates:
            if remaining <= 0:
                break
            if tx.total_amount <= remaining + 1e-9:  # float tolerance
                settled_ids.append(tx.id)
                remaining -= tx.total_amount
            else:
                # Partial settlement not supported at transaction level —
                # skip this tx and continue to next that fits.
                continue

        return self._ledger.settle(settled_ids) if settled_ids else []
