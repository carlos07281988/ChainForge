"""ChainForge Enterprise: Agent Justice Protocol example.

Usage:
    python examples/enterprise/justice_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.justice import (
    JusticeGuard, EvidencePack, EvidenceItem,
    DecisionReview, DecisionTree, DecisionNode,
    AppealRequest, AppealEngine,
)

async def main():
    print("=== Agent Justice Protocol ===\n")

    # 1. Build evidence pack (normally auto-collected by JusticeGuard middleware)
    evidence = EvidencePack(
        run_id="run-abc123",
        agent_name="refund-processor",
        tools_available=["refund_tool", "email_tool", "query_db"],
        items=[
            EvidenceItem(step=1, event_type="user_input", content="I want a refund for order #12345, the amount is $150"),
            EvidenceItem(step=2, event_type="llm_call", content="Need to look up the order first", model="gpt-4o", tokens_used=200, cost=0.002),
            EvidenceItem(step=3, event_type="tool_call", tool_name="query_db", tool_args={"query": "order #12345"}),
            EvidenceItem(step=4, event_type="tool_result", tool_name="query_db", tool_result={"order_id": "12345", "amount": 50.0}),
            EvidenceItem(step=5, event_type="llm_call", content="The order amount is $50, processing refund", model="gpt-4o", tokens_used=150, cost=0.0015),
            EvidenceItem(step=6, event_type="tool_call", tool_name="refund_tool", tool_args={"order_id": "12345", "amount": 50.0}),
            EvidenceItem(step=7, event_type="tool_result", tool_name="refund_tool", tool_result={"status": "refunded", "amount": 50.0}),
            EvidenceItem(step=8, event_type="final_output", content="Refund of $50 has been processed"),
        ],
        total_steps=8, total_tokens=350, total_cost=0.0035, duration_ms=1200,
    )
    evidence.total_steps = len(evidence.items)
    print("1. Evidence Pack:")
    print(evidence.timeline())

    # 2. Decision tree
    tree = DecisionTree(nodes={
        "root": DecisionNode(id="root", label="User requests $150 refund", type="input", children=["llm1"]),
        "llm1": DecisionNode(id="llm1", label="LLM: Look up order", type="llm", children=["tool1"], decision_rationale="Need to verify order amount"),
        "tool1": DecisionNode(id="tool1", label="Tool: query_db('order #12345')", type="tool", children=["llm2"]),
        "llm2": DecisionNode(id="llm2", label="LLM: Order shows $50, not $150", type="llm", children=["tool2"], decision_rationale="System shows $50, proceed with $50 refund"),
        "tool2": DecisionNode(id="tool2", label="Tool: refund_tool($50)", type="tool", children=["output"]),
        "output": DecisionNode(id="output", label="Output: Refunded $50", type="output"),
    }, root_id="root")
    print("\n2. Decision Tree:")
    print(tree.to_mermaid())

    # 3. Appeal engine
    engine = AppealEngine()

    # User submits appeal
    appeal = engine.submit(AppealRequest(
        run_id="run-abc123",
        reason="The refund was $50, but I paid $150 for this order",
        raised_by="carlos@example.com",
        severity="high",
    ))
    print(f"\n3. Appeal Submitted:")
    print(f"   ID: {appeal.appeal_id}")
    print(f"   Reason: {appeal.reason}")

    # Generate review
    review = engine.generate_review(appeal, evidence, tree)
    print(f"\n4. Decision Review:")
    print(review.summary())

    # Human appeal verdict
    verdict = await engine.human_appeal(appeal, "dpo@acme-corp.com", review)
    print(f"\n5. Human Appeal:")
    print(f"   Reviewer: {verdict.reviewed_by}")
    print(f"   Action: {'Upheld' if verdict.upheld else 'Overturned — ' + verdict.override_action}")

    # Stats
    print(f"\n6. Appeal Stats: {engine.stats}")

if __name__ == "__main__":
    asyncio.run(main())
