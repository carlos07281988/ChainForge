"""ChainForge Enterprise: Collective Agent Memory example.

Usage:
    python examples/enterprise/collective_example.py
"""
import asyncio, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.collective import (
    CollectiveMemory, Experience, ForgettingCurve,
    ExperienceRetriever, ConflictResolver,
)

async def main():
    print("=== Collective Agent Memory ===\n")

    # 1. Create shared memory
    cm = CollectiveMemory(namespace="customer-support", forgetting_curve="ebbinghaus")
    print(f"1. Collective Memory: namespace='{cm.namespace}', curve='ebbinghaus'")

    # 2. Agents add experiences
    now = time.time()
    cm.add(Experience(id="exp-1", task="refund customer order #A123", task_type="refund",
        tools_used=["refund_tool", "email_tool"], model_used="gpt-4o",
        outcome="success", cost=0.05, tokens=520, duration_ms=800, timestamp=now - 86400))
    cm.add(Experience(id="exp-2", task="refund request #B456 without email", task_type="refund",
        tools_used=["refund_tool"], model_used="gpt-4o-mini",
        outcome="failure", feedback="Customer complained -- no confirmation email sent",
        cost=0.01, tokens=200, duration_ms=400, timestamp=now - 43200))
    cm.add(Experience(id="exp-3", task="refund order #C789", task_type="refund",
        tools_used=["refund_tool", "email_tool"], model_used="gpt-4o",
        outcome="success", cost=0.04, tokens=480, duration_ms=700, timestamp=now - 3600))
    cm.add(Experience(id="exp-4", task="check account balance", task_type="account_inquiry",
        tools_used=["query_db"], model_used="gpt-4o-mini",
        outcome="success", cost=0.005, tokens=150, duration_ms=300, timestamp=now))

    print(f"   Stored {cm.count} experiences")
    print(f"   Task types: refund (3), account_inquiry (1)")

    # 3. Forgetting curve
    d7 = ForgettingCurve.ebbinghaus(7.0)  # 7 days
    d0 = ForgettingCurve.ebbinghaus(0.0)  # fresh
    print(f"\n2. Ebbinghaus Forgetting Curve:")
    print(f"   Day 0:  {d0:.3f} (fresh)")
    print(f"   Day 7:  {d7:.3f} (half-life)")
    print(f"   Day 30: {ForgettingCurve.ebbinghaus(30.0):.3f}")
    print(f"   Day 90: {ForgettingCurve.ebbinghaus(90.0):.3f}")

    # 4. Experience retrieval
    retriever = ExperienceRetriever(cm)
    results = retriever.search("refund", limit=3, min_success_rate=0.5)
    print(f"\n3. Experience Retrieval (query='refund', min_success_rate=0.5):")
    for i, exp in enumerate(results):
        icon = "SUCCESS" if exp.outcome == "success" else "FAILURE"
        print(f"   {icon} {exp.task} (cost: ${exp.cost:.2f}, decay: {exp.decay_factor:.3f})")

    # 5. Conflict resolution
    resolver = ConflictResolver(cm)
    conflicts = resolver.find_conflicts()
    print(f"\n4. Conflict Resolution:")
    for c in conflicts:
        print(f"   Task: {c.task_type}")
        print(f"   Agent A: {c.agent_a_outcome}")
        print(f"   Agent B: {c.agent_b_outcome}")
        print(f"   Resolution: {c.resolution}")
        print(f"   Recommendation: {c.recommendation}")
        print(f"   Confidence: {c.confidence:.0%}")

    # 6. Export
    data = cm.export()
    print(f"\n5. Export: {len(data)} experiences ready for analytics pipeline")

if __name__ == "__main__":
    asyncio.run(main())
