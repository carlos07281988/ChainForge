"""ChainForge Enterprise: Agent Capability Registry example.

Usage:
    python examples/enterprise/registry_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.registry import (
    CapabilityRegistry, AgentProfile, ServiceLevelAgreement, AutoNegotiation,
)

async def main():
    print("=== Agent Capability Registry (DNS for Agents) ===\n")

    registry = CapabilityRegistry(namespace="acme-corp")

    # 1. Register agents with their capabilities
    registry.register(AgentProfile(
        agent_id="agent-db-01", name="PostgreSQL Agent", version="2.1.0",
        capabilities=["postgresql:query", "postgresql:schema", "sql:generate"],
        tools_exposed=["query_db", "get_schema", "explain_query"],
        endpoints={"a2a": "a2a://db-agent.acme.com", "http": "https://db-agent.acme.com/api"},
        health_check_url="https://db-agent.acme.com/health",
        pricing={"per_query": 0.001},
        sla=ServiceLevelAgreement(max_latency_ms=500, availability=0.999),
    ))

    registry.register(AgentProfile(
        agent_id="agent-email-01", name="Email Agent", version="1.0.0",
        capabilities=["email:send", "email:template", "email:track"],
        tools_exposed=["send_email", "render_template"],
        endpoints={"a2a": "a2a://email-agent.acme.com"},
        pricing={"per_email": 0.0005},
        sla=ServiceLevelAgreement(max_latency_ms=200, availability=0.995),
    ))

    registry.register(AgentProfile(
        agent_id="agent-s3-01", name="S3 Storage Agent", version="3.0.1",
        capabilities=["s3:upload", "s3:download", "s3:list", "s3:delete"],
        tools_exposed=["upload_file", "download_file", "list_bucket"],
        endpoints={"http": "https://s3-agent.acme.com/api"},
        pricing={"per_gb": 0.01},
    ))

    print(f"1. Registered {len(registry.list_all())} agents:")
    for p in registry.list_all():
        print(f"   {p.name} v{p.version} — {', '.join(p.capabilities[:3])}")

    # 2. Discover by exact capability
    matches = await registry.discover(capability="postgresql:query")
    print(f"\n2. Discovery (capability='postgresql:query'):")
    for profile, score in matches:
        print(f"   {profile.name} (score: {score:.2f}, ${profile.pricing.get('per_query', 0):.4f}/query)")

    # 3. Discover by keyword search
    matches = await registry.discover(query="send messages")
    print(f"\n3. Discovery (query='send messages'):")
    for profile, score in matches:
        print(f"   {profile.name} (score: {score:.2f})")

    # 4. Auto-negotiation
    neg = AutoNegotiation(
        requester_id="agent-support-bot",
        capability_needed="s3:upload",
        constraints={"max_cost_per_call": 0.02},
        registry=registry,
    )
    result = await neg.start()
    print(f"\n4. Auto-Negotiation (need=s3:upload):")
    print(f"   Accepted: {result.accepted}")
    if result.provider:
        print(f"   Provider: {result.provider.name}")
        print(f"   Contract: {result.contract}")
        print(f"   Alternatives: {[p.name for p in result.alternatives]}")

    # 5. Health check
    health = await registry.health_check("agent-db-01")
    print(f"\n5. Health Check (agent-db-01): {'online' if health else 'offline'}")

if __name__ == "__main__":
    asyncio.run(main())
