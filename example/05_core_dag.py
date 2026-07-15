"""example/05_core_dag.py — DAG graph execution verification."""
import sys, asyncio
from chainforge.core.graph import DAG, Node, Edge, GraphContext
from chainforge.core.graph import GraphNodeType, DAGNodeType
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_dag_init():
    dag = DAG(name="test")
    check("d1: name", dag.name == "test")
    check("d2: no nodes", len(dag.nodes) == 0)

def test_dag_add_node():
    dag = DAG(name="test")
    dag.add_node("step1", fn=lambda x: x + 1)
    check("d3: has node", "step1" in dag.nodes)
    check("d4: fn set", dag.nodes["step1"].fn is not None)

def test_dag_add_edge():
    dag = DAG(name="test")
    dag.add_node("a").add_node("b").add_edge("a", "b")
    check("d5: edge count", len(dag.edges) == 1)
    check("d6: edge source", dag.edges[0].source == "a")
    check("d7: edge target", dag.edges[0].target == "b")

def test_dag_missing_edge():
    dag = DAG(name="test")
    dag.add_node("a")
    try:
        dag.add_edge("a", "missing")
        check("d8: should raise ValueError", False)
    except ValueError:
        check("d8: raises on missing node", True)

def test_dag_topological_linear():
    dag = DAG(name="test")
    for n in ["a", "b", "c"]:
        dag.add_node(n)
    dag.add_edge("a", "b").add_edge("b", "c")
    order = dag._topological_sort()
    check("d9: linear order", order == ["a", "b", "c"])

def test_dag_topological_diamond():
    dag = DAG(name="test")
    for n in ["a", "b", "c", "d"]:
        dag.add_node(n)
    dag.add_edge("a", "b").add_edge("a", "c")
    dag.add_edge("b", "d").add_edge("c", "d")
    order = dag._topological_sort()
    check("da: diamond start a", order[0] == "a")
    check("db: diamond end d", order[-1] == "d")
    check("dc: diamond middle", set(order[1:3]) == {"b", "c"})

def test_dag_cycle():
    dag = DAG(name="test")
    dag.add_node("a").add_node("b")
    dag.add_edge("a", "b").add_edge("b", "a")
    try:
        dag._topological_sort()
        check("dd: should detect cycle", False)
    except ValueError:
        check("dd: cycle detected", True)

async def test_dag_run():
    dag = DAG(name="test")
    dag.add_node("double", fn=lambda x: x * 2)
    dag.add_node("add_one", fn=lambda x: x + 1)
    dag.add_edge("double", "add_one")
    stream = dag.run(5)
    events = await stream.collect()
    has_status = any(e.type.value == "status" for e in events)
    check("de: run produces events", len(events) > 0)
    check("df: has status events", has_status)

def test_node_types():
    from chainforge.core.graph import Node
    n = Node(id="test", type=GraphNodeType.agent, description="An agent node")
    check("nt1: node type", n.type == GraphNodeType.agent)
    check("nt2: node id", n.id == "test")
    check("nt3: node desc", n.description == "An agent node")

async def main():
    print("=" * 58)
    print("  Core DAG \u2014 graph construction, topology, execution")
    print("=" * 58)
    test_dag_init(); test_dag_add_node(); test_dag_add_edge()
    test_dag_missing_edge(); test_dag_topological_linear()
    test_dag_topological_diamond(); test_dag_cycle()
    await test_dag_run(); test_node_types()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
