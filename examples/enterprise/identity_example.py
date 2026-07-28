"""ChainForge Enterprise: Agent Identity & Reputation example.

Usage:
    python examples/enterprise/identity_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.identity import (
    AgentIdentity, ReputationEngine, TrustPolicy, TrustRule,
    VerifiableCredential,
)

async def main():
    print("=== Agent Identity & Reputation Protocol ===\n")

    # 1. Create agent identity (Ed25519 keypair)
    identity = AgentIdentity.create(
        name="customer-support-bot",
        organization="acme-corp",
        capabilities=["chat", "refund_processing", "order_lookup"],
    )
    print(f"1. Agent Identity:")
    print(f"   Agent ID: {identity.agent_id}")
    print(f"   DID:      {identity.did}")
    print(f"   Organization: {identity.organization}")
    print(f"   Capabilities: {identity.capabilities}")

    # 2. Sign and verify messages
    payload = b"Authorize refund for order #12345"
    signature = identity.sign(payload)
    verified = AgentIdentity.verify(payload, signature, identity.public_key)
    print(f"\n2. Message Signing:")
    print(f"   Payload: {payload.decode()}")
    print(f"   Signature: {signature[:40]}...")
    print(f"   Verified: {verified}")
    print(f"   Tampered: {not AgentIdentity.verify(b'tampered', signature, identity.public_key)}")

    # 3. Reputation engine
    engine = ReputationEngine()
    for i in range(100):
        engine.record_event(identity.agent_id, "successful_call", latency_ms=100 + i % 50)
    for i in range(3):
        engine.record_event(identity.agent_id, "accurate_tool_choice")
    # One security incident
    engine.record_event(identity.agent_id, "prompt_injection_attempt")

    score = engine.score(identity.agent_id)
    print(f"\n3. Reputation Score:")
    print(f"   Overall:     {score.overall}/100")
    print(f"   Reliability: {score.reliability}/100")
    print(f"   Safety:      {score.safety}/100  (penalized for injection)")
    print(f"   Accuracy:    {score.accuracy}/100")
    print(f"   Total calls: {score.total_calls}")
    print(f"   Incidents:   {score.incident_count}")

    # 4. Trust Policy
    policy = TrustPolicy(rules=[
        TrustRule(min_reputation=80, action="allow", reason="High-reputation agent"),
        TrustRule(max_reputation=50, action="block_all_tools", reason="Low trust"),
    ])
    decision = policy.evaluate(score)
    print(f"\n4. Trust Decision:")
    print(f"   Score {score.overall} -> Allowed: {decision.allowed}")
    print(f"   Action: {decision.action}")

    # 5. Verifiable Credentials (cross-org trust)
    vc = VerifiableCredential.issue(
        issuer=identity,
        subject_id="partner-agent-001",
        claims={"role": "data-reader", "tier": "premium"},
        expires_in_days=180,
    )
    print(f"\n5. Verifiable Credential:")
    print(f"   Issuer:  {vc.issuer_id}")
    print(f"   Subject: {vc.subject_id}")
    print(f"   Claims:  {vc.claims}")
    print(f"   Expires: {vc.expires_at - vc.issued_at:.0f}s from now")
    print(f"   Valid:   {vc.verify(identity.public_key)}")

if __name__ == "__main__":
    asyncio.run(main())
