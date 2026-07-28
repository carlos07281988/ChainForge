"""ChainForge Enterprise: Agent Economic Protocol example.

Usage:
    python examples/enterprise/economy_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.economy import AgentEconomy, BillingContract
from chainforge.enterprise.economy import CreditLedger, Transaction

async def main():
    print("=== Agent Economic Protocol ===\n")

    economy = AgentEconomy(settlement_currency="usd")

    # 1. Register seller contracts
    economy.register_contract("seller-db", BillingContract(
        pricing={"per_tool_call": 0.05, "per_token": 0.00001},
        free_quota=100,
    ))
    economy.register_contract("seller-email", BillingContract(
        pricing={"per_tool_call": 0.01},
    ))
    print("1. Seller Contracts Registered:")
    print("   seller-db: $0.05/tool_call + $0.00001/token (100 free/day)")
    print("   seller-email: $0.01/tool_call")

    # 2. Record transactions
    ledger = economy._ledger
    ledger.record(Transaction(from_agent_id="buyer-support", to_agent_id="seller-db",
        tool_name="query_db", pricing_model="per_tool_call",
        unit_price=0.05, quantity=50, total_amount=2.50))
    ledger.record(Transaction(from_agent_id="buyer-support", to_agent_id="seller-db",
        tool_name="explain_query", pricing_model="per_tool_call",
        unit_price=0.05, quantity=30, total_amount=1.50))
    ledger.record(Transaction(from_agent_id="buyer-support", to_agent_id="seller-email",
        tool_name="send_email", pricing_model="per_tool_call",
        unit_price=0.01, quantity=200, total_amount=2.00))

    # 3. Buyer invoice — items have: to_agent_id, tool_name, count, subtotal
    inv = economy.invoice("buyer-support")
    print("\n2. Buyer Invoice (buyer-support):")
    print(f"   Total payable: ${inv.total_payable:.2f}")
    for item in inv.items:
        print(f"   -> {item['to_agent_id']}/{item['tool_name']}: ${item['subtotal']:.2f} ({item['count']} calls)")

    # 4. Seller revenue
    rev = economy.revenue("seller-db")
    print("\n3. Seller Revenue (seller-db):")
    print(f"   Total earned: ${rev.total_earned:.2f}")
    print(f"   Outstanding: ${rev.total_outstanding:.2f}")
    print(f"   Settled: ${rev.total_settled:.2f}")

    # 5. Settle transaction
    settled = economy.settle("buyer-support", "seller-db", 2.50, method="internal")
    print("\n4. Settlement:")
    print("   buyer-support -> seller-db: $2.50")
    print(f"   Settled transactions: {len(settled)}")

    rev_after = economy.revenue("seller-db")
    print(f"   Revenue after settle: ${rev_after.total_earned:.2f}")
    print(f"   Settled after: ${rev_after.total_settled:.2f}")
    print(f"   Outstanding after: ${rev_after.total_outstanding:.2f}")

    # 6. Balance check
    balance_buyer = ledger.balance("buyer-support")
    balance_seller = ledger.balance("seller-db")
    print("\n5. Balances (unsettled only):")
    print(f"   buyer-support: ${balance_buyer:+.2f} (negative = debtor)")
    print(f"   seller-db: ${balance_seller:+.2f} (positive = creditor)")

if __name__ == "__main__":
    asyncio.run(main())
