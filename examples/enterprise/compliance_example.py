"""ChainForge Enterprise: EU AI Act Compliance Engine example.

Usage:
    python examples/enterprise/compliance_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.compliance import (
    RiskClassifier, RiskRule, RiskTier,
    HITLPolicy, ComplianceAuditor, ComplianceGuard,
)

async def main():
    print("=== EU AI Act Compliance Engine ===\n")

    # 1. Risk Classification -- automatic risk tier assessment
    classifier = RiskClassifier()
    tier, rules = classifier.classify(
        tools=["delete_file", "query_db", "send_email"],
        data_labels=["pii"],
        domain="healthcare",
    )
    print(f"1. Risk Classification:")
    print(f"   Tools: delete_file, query_db, send_email")
    print(f"   Data labels: pii")
    print(f"   Domain: healthcare")
    print(f"   -> Risk Tier: {tier.value.upper()}")
    for r in rules:
        print(f"     Trigger: {r.reason}")
    print()

    # 2. HITL Policy -- human approval for high-risk actions
    async def my_approval_handler(request):
        print(f"   [HITL] Approval requested for: {request.action[:60]}...")
        return True  # Auto-approve for demo

    policy = HITLPolicy(
        require_approval_on=[RiskTier.HIGH, RiskTier.LIMITED],
        approval_handler=my_approval_handler,
    )
    print(f"2. HITL Policy:")
    print(f"   Requires approval on: {[t.value for t in policy.require_approval_on]}")
    print(f"   Needing approval (HIGH): {policy.needs_approval(RiskTier.HIGH)}")
    print(f"   Needing approval (LOW): {policy.needs_approval(RiskTier.MINIMAL)}")
    print()

    # 3. Compliance Auditor -- generate compliance reports
    auditor = ComplianceAuditor(log_path=":memory:", regulation="eu-ai-act-2026")
    auditor.record("risk_classification", {"risk_tier": "high", "triggers": ["Tool can delete data"]})
    auditor.record("hitl_required", {"agent": "support-bot"})
    auditor.record("hitl_approved", {"reviewer": "ops-team"})

    report = auditor.generate(risk_tier="high", has_hitl=True)
    print(f"3. Compliance Report:")
    print(f"   Score: {report.compliance_score:.0%}")
    print(f"   Total events: {report.total_events}")
    for check in report.checks:
        icon = "PASS" if check.status == "compliant" else "FAIL"
        print(f"   {icon} Art.{check.article} {check.requirement}")
    print()
    print(report.to_markdown())
    auditor.close()

if __name__ == "__main__":
    asyncio.run(main())
