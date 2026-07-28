"""ChainForge Enterprise: Agent Mesh Networking example.

Usage:
    python examples/enterprise/mesh_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.mesh import MeshRegistry, MeshPeer, MeshRouter, MeshCluster, MeshNode

async def main():
    print("=== Agent Mesh Networking ===\n")

    registry = MeshRegistry()

    # 1. Register mesh peers across regions
    peers = [
        MeshPeer(node_id="node-us-1", region="us-east",
            endpoint="https://node-us-1.internal/agent",
            capabilities=["postgresql:query", "email:send"]),
        MeshPeer(node_id="node-us-2", region="us-west",
            endpoint="https://node-us-2.internal/agent",
            capabilities=["postgresql:query"]),
        MeshPeer(node_id="node-eu-1", region="eu-west",
            endpoint="https://node-eu-1.internal/agent",
            capabilities=["postgresql:query", "email:send", "s3:upload"]),
        MeshPeer(node_id="node-cn-1", region="cn-north",
            endpoint="https://node-cn-1.internal/agent",
            capabilities=["postgresql:query", "email:send"]),
    ]
    for p in peers:
        registry.register(p)

    print("1. Mesh Peers across regions:")
    for p in registry.list_all():
        print(f"   {p.node_id} [{p.region}] -- {', '.join(p.capabilities[:3])}")

    # 2. Simulate region failover (set peer offline manually)
    print(f"\n2. Simulating eu-west region failure...")
    for peer in registry.list_all():
        if peer.node_id == "node-eu-1":
            peer.status = "offline"
    online = sum(1 for p in registry.list_all() if p.status == "online")
    offline = sum(1 for p in registry.list_all() if p.status == "offline")
    print(f"   Online: {online}, Offline: {offline}")

    # 3. Route with auto-failover
    router = MeshRouter()
    result = router.select(
        registry=registry,
        capability="postgresql:query",
        region_preference="eu-west",    # Prefer EU, but it's down
        auto_failover=True,             # -> Fall back to us-east
    )
    print(f"\n3. Auto-Failover Routing:")
    print(f"   Preferred: eu-west (OFFLINE)")
    if result:
        print(f"   Selected:  {result.node_id} [{result.region}]")
        print(f"   Endpoint:  {result.endpoint}")

    # 4. Cluster management with MeshNode objects
    # Dummy agent callable for demo
    def dummy_agent(payload):
        return {"status": "ok", "payload": payload}

    cluster = MeshCluster(name="production")
    cluster.add_node(MeshNode(
        agent=dummy_agent, region="us-east", mesh_registry=registry,
        capabilities=["postgresql:query", "email:send"], port=8080,
    ))
    cluster.add_node(MeshNode(
        agent=dummy_agent, region="us-west", mesh_registry=registry,
        capabilities=["postgresql:query"], port=8080,
    ))
    cluster.add_node(MeshNode(
        agent=dummy_agent, region="eu-west", mesh_registry=registry,
        capabilities=["postgresql:query", "email:send", "s3:upload"], port=8080,
    ))
    cluster.add_node(MeshNode(
        agent=dummy_agent, region="cn-north", mesh_registry=registry,
        capabilities=["postgresql:query", "email:send"], port=8080,
    ))

    summary = cluster.health_summary()
    print(f"\n4. Cluster Health:")
    print(f"   Name: {summary['cluster_name']}")
    print(f"   Total nodes: {summary['total_nodes']}")
    print(f"   Regions: {summary['regions']}")
    print(f"   Healthy: {summary['healthy']}")

    plan = cluster.failover_plan()
    print(f"\n5. Failover Plan:")
    for region, nodes in plan.get("by_region", {}).items():
        print(f"   {region}: {[n['node_id'] for n in nodes]}")

if __name__ == "__main__":
    asyncio.run(main())
