"""example/13_guardrails.py — Guardrail protocol verification."""
import sys, asyncio
from chainforge.guardrails import GuardrailResult, GuardrailAction, GuardrailSeverity
from chainforge.guardrails.base import Guardrail
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_guardrail_result_defaults():
    r = GuardrailResult()
    check("gr1: passed default True", r.passed is True)
    check("gr2: action default block", r.action == GuardrailAction.block)
    check("gr3: severity default low", r.severity == GuardrailSeverity.low)
    check("gr4: risk score default 0", r.risk_score == 0.0)

def test_guardrail_result_custom():
    r = GuardrailResult(
        passed=False, action=GuardrailAction.block,
        severity=GuardrailSeverity.critical,
        reason="Inappropriate content", category="safety",
        risk_score=0.95,
    )
    check("gr5: custom passed", r.passed is False)
    check("gr6: custom reason", r.reason == "Inappropriate content")
    check("gr7: custom risk", r.risk_score == 0.95)
    check("gr8: custom category", r.category == "safety")

def test_actions():
    check("ga1: block", GuardrailAction.block.value == "block")
    check("ga2: flag", GuardrailAction.flag.value == "flag")
    check("ga3: rewrite", GuardrailAction.rewrite.value == "rewrite")
    check("ga4: warn", GuardrailAction.warn.value == "warn")

def test_severities():
    check("gs1: low", GuardrailSeverity.low.value == "low")
    check("gs2: medium", GuardrailSeverity.medium.value == "medium")
    check("gs3: high", GuardrailSeverity.high.value == "high")
    check("gs4: critical", GuardrailSeverity.critical.value == "critical")

def test_result_metadata():
    r = GuardrailResult(metadata={"user_id": "u1", "source": "input"})
    check("gm1: metadata set", r.metadata["user_id"] == "u1")
    check("gm2: metadata source", r.metadata["source"] == "input")

async def main():
    print("=" * 58)
    print("  Guardrails \u2014 GuardrailResult, actions, severities")
    print("=" * 58)
    test_guardrail_result_defaults(); test_guardrail_result_custom()
    test_actions(); test_severities(); test_result_metadata()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
