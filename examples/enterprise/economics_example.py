"""ChainForge Enterprise: Agent Economics Layer example.

Usage:
    python examples/enterprise/economics_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.economics import CostTracker, BudgetGuard, CostReport
from chainforge.enterprise.economics.ledger import CostRecord

async def main():
    print("=== Agent Economics Layer ===\n")

    # 1. CostTracker -- record and query costs
    tracker = CostTracker(backend="memory")

    # Simulate recording some LLM calls
    ledger = tracker._ledger
    ledger.record(CostRecord(model="gpt-4o", provider="openai",
        input_tokens=350, output_tokens=120, cost=0.0085,
        attribution={"project": "customer-support", "department": "ops"}))
    ledger.record(CostRecord(model="gpt-4o-mini", provider="openai",
        input_tokens=150, output_tokens=50, cost=0.0004,
        attribution={"project": "customer-support", "department": "ops"}))
    ledger.record(CostRecord(model="gpt-4o", provider="openai",
        input_tokens=800, output_tokens=300, cost=0.0220,
        attribution={"project": "internal-qa", "department": "engineering"}))

    print("1. Cost Report (by model):")
    report = tracker.report(group_by="model")
    print(f"   Total: ${report.total:.4f}")
    for row in report.to_json():
        print(f"   {row['dimension']}: ${row['total_cost']:.4f} ({row['calls']} calls)")

    print("\n2. Cost Report (by project):")
    report = tracker.report(group_by="project")
    for row in report.to_json():
        print(f"   {row['dimension']}: ${row['total_cost']:.4f} ({row['calls']} calls)")

    # 2. BudgetGuard -- enforce spending limits
    guard = BudgetGuard(
        daily_limit=0.01,
        on_limit="warn",  # warn only for demo
    )
    print(f"\n3. BudgetGuard:")
    print(f"   Daily limit: ${guard.daily_limit:.2f}")
    print(f"   On limit: warn (log and continue)")
    print(f"   (In production: downgrade, block, or warn)")

    # 3. Optimization suggestions
    suggestions = tracker.optimize(period="last-30-days")
    if suggestions.items:
        print(f"\n4. Cost Optimization Suggestions:")
        print(f"   Potential savings: ${suggestions.potential_savings:.2f}")
        for item in suggestions.items:
            print(f"   -> {item}")
    else:
        print(f"\n4. Cost Optimization: No suggestions (need more data)")

    tracker.close()

if __name__ == "__main__":
    asyncio.run(main())
