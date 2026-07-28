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
"""Middleware that auto-records billing transactions for cross-agent tool calls.

Wraps an agent runtime's streaming event loop so that every tool-call
event flowing from one agent to another is captured as a :class:`Transaction`
in the economy's ledger.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, AsyncIterator

from chainforge.enterprise.economy.contract import BillingContract, Transaction


def billing_middleware(
    economy,  # AgentEconomy (lazy import to avoid circular reference)
    billing_contract: BillingContract | None = None,
    role: str = "buyer",
) -> Callable[..., Any]:
    """Create async middleware that auto-records cross-agent transactions.

    Parameters
    ----------
    economy:
        The :class:`AgentEconomy` instance whose ledger receives new records.
    billing_contract:
        Pricing contract for the seller.  When omitted every tool call is
        priced at the default ``per_tool_call`` rate.
    role:
        ``"buyer"`` or ``"seller"`` — controls which side of the transaction
        this middleware represents.

    Returns
    -------
    Callable
        An async middleware function compatible with common agent runtimes
        (e.g. ``(messages, ctx, next_handler) -> AsyncIterator[Event]``).
    """

    default_price = 0.001
    if billing_contract is not None:
        default_price = billing_contract.pricing.get("per_tool_call", default_price)

    async def _mw(
        messages: Any, ctx: Any, next_handler: Callable[..., AsyncIterator[Any]]
    ) -> AsyncIterator[Any]:
        async for event in next_handler(messages, ctx):
            # Check whether this event signals a cross-agent tool call
            if _is_tool_call_event(event):
                cross_agent_info = _extract_cross_agent_context(ctx)
                if cross_agent_info is not None:
                    to_agent = cross_agent_info.get("to_agent_id", "")
                    tool_name = cross_agent_info.get("tool_name", "")

                    # Determine pricing
                    if billing_contract is not None:
                        price = billing_contract.pricing.get(tool_name, default_price)
                    else:
                        price = default_price

                    tx = Transaction(
                        from_agent_id=cross_agent_info.get("from_agent_id", ""),
                        to_agent_id=to_agent,
                        tool_name=tool_name,
                        pricing_model="per_tool_call",
                        unit_price=price,
                        quantity=1,
                        total_amount=price,
                    )
                    economy._ledger.record(tx)

            yield event

    return _mw


def _is_tool_call_event(event: Any) -> bool:
    """Return ``True`` if *event* looks like a tool-call event.

    Tries several common shapes (dict with ``type``, object with
    ``event`` attribute, etc.) so the middleware works across
    different agent runtimes.
    """
    if isinstance(event, dict):
        return event.get("type", "") in ("tool_call", "tool_use", "tool_start")
    if hasattr(event, "type"):
        return getattr(event, "type", "") in ("tool_call", "tool_use", "tool_start")
    return False


def _extract_cross_agent_context(ctx: Any) -> dict[str, str] | None:
    """Attempt to pull cross-agent billing info from the runtime context.

    Returns a dict with keys ``from_agent_id``, ``to_agent_id``,
    ``tool_name`` when available, or ``None`` if the current call is
    not a cross-agent invocation.
    """
    if ctx is None:
        return None

    # ctx can be a dict, an object with attributes, or a Pydantic model
    to_agent = _safe_getattr(ctx, "to_agent_id") or _safe_getattr(ctx, "target_agent_id")
    if to_agent is None:
        return None

    info: dict[str, str] = {
        "from_agent_id": _safe_getattr(ctx, "agent_id") or "",
        "to_agent_id": to_agent,
        "tool_name": _safe_getattr(ctx, "tool_name") or "",
    }
    return info


def _safe_getattr(obj: Any, name: str) -> str | None:
    """Safely read attribute *name* from *obj* (dict or object)."""
    if isinstance(obj, dict):
        return obj.get(name)
    if hasattr(obj, name):
        val = getattr(obj, name, None)
        if val is not None:
            return str(val)
    # Try model_dump / dict for Pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            data = obj.model_dump()
            if isinstance(data, dict) and name in data:
                val = data[name]
                if val is not None:
                    return str(val)
        except Exception:
            pass
    return None
