"""ChainForge Enterprise: GraphRAG 3.0 Knowledge Graph Engine example.

Usage:
    python examples/enterprise/graphrag_example.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.graphrag import (
    GraphRAGEngine, Node, Edge, GraphMemory, GraphQLQuery,
)

async def main():
    print("=== GraphRAG 3.0: Multi-Agent Knowledge Graph ===\n")

    engine = GraphRAGEngine()

    # 1. Build a knowledge graph
    customer = engine.add_node(Node(type="Customer", label="carlos@example.com",
        properties={"name": "Carlos", "plan": "enterprise"}))
    order_a = engine.add_node(Node(type="Order", label="order-A123",
        properties={"amount": 150.0, "date": "2026-07-15"}))
    order_b = engine.add_node(Node(type="Order", label="order-B456",
        properties={"amount": 300.0, "date": "2026-07-20"}))
    product = engine.add_node(Node(type="Product", label="ChainForge Pro",
        properties={"price": 150.0, "category": "software"}))
    support = engine.add_node(Node(type="Agent", label="support-bot",
        properties={"role": "customer-support"}))

    engine.add_edge(Edge(source_id=customer.id, target_id=order_a.id,
        type="PURCHASED", label="Bought order A123"))
    engine.add_edge(Edge(source_id=customer.id, target_id=order_b.id,
        type="PURCHASED", label="Bought order B456"))
    engine.add_edge(Edge(source_id=order_a.id, target_id=product.id,
        type="CONTAINS", label="Contains ChainForge Pro"))
    engine.add_edge(Edge(source_id=support.id, target_id=order_a.id,
        type="PROCESSED", label="Handled order A123"))

    print(f"1. Graph Stats:")
    print(f"   Nodes: {engine.stats['nodes']} ({', '.join(engine.stats['node_types'].keys())})")
    print(f"   Edges: {engine.stats['edges']}")

    # 2. Traversal -- find neighbors
    nbrs = engine.neighbors(customer.id, direction="out")
    print(f"\n2. Carlos's Purchases (outgoing edges):")
    for n in nbrs:
        print(f"   -> {n.type}: {n.label}")

    # 3. Path finding
    paths = engine.path(support.id, product.id, max_depth=3)
    print(f"\n3. Path: support-bot -> ChainForge Pro:")
    if paths:
        for path in paths:
            labels = [engine.get_node(nid).label for nid in path if engine.get_node(nid)]
            print(f"   {' -> '.join(labels)}")

    # 4. Graph-native memory
    memory = GraphMemory(engine)
    memory.remember("Tool", "refund_tool", {"type": "financial", "risk": "medium"})
    memory.link("carlos@example.com", "refund_tool", "USES")
    ctx = memory.recall("carlos@example.com")
    print(f"\n4. Graph Memory -- Carlos context:")
    print(f"   Entity: {ctx['entity']['label']}")
    for rel in ctx['relations']:
        print(f"   - [{rel['type']}] -> {rel.get('target', rel.get('source', '?'))}")

    # 5. Keyword search
    results = engine.search("ChainForge Pro", limit=3)
    print(f"\n5. Semantic Search 'ChainForge Pro':")
    for sg in results:
        node_labels = [n.label for n in sg.nodes]
        print(f"   Found: {node_labels} (score: {sg.score})")

    # 6. GraphQL query
    gql = GraphQLQuery(query="all", node_type="Customer")
    results = engine.execute(gql)
    print(f"\n6. GraphQL (node_type='Customer'):")
    for r in results:
        print(f"   {r['label']} -- plan: {r['properties'].get('plan', 'unknown')}")

if __name__ == "__main__":
    asyncio.run(main())
