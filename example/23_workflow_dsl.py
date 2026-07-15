"""example/23_workflow_dsl.py — Workflow DSL verification."""
import sys
from chainforge.core.graph_dsl import parse_workflow_dict, parse_workflow_json, workflow_to_dict, WorkflowDef, WorkflowNodeDef
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

wf = WorkflowDef(name="test", nodes=[
    WorkflowNodeDef(id="a", type="entry"),
    WorkflowNodeDef(id="b", type="exit"),
])
c("WorkflowDef", wf.name == "test")
c("2 nodes", len(wf.nodes) == 2)

graph = parse_workflow_dict({
    "name":"demo","nodes":[
        {"id":"start","type":"entry"},
        {"id":"end","type":"exit"}],
    "edges":[{"source":"start","target":"end"}]
})
c("graph from dict", graph.name == "demo")
c("2 graph nodes", len(graph.nodes) == 2)
c("1 graph edge", len(graph.edges) == 1)

graph2 = parse_workflow_json('{"name":"j","nodes":[{"id":"s","type":"entry"},{"id":"e","type":"exit"}],"edges":[{"source":"s","target":"e"}]}')
c("graph from json", graph2.name == "j")

d = workflow_to_dict(graph)
c("roundtrip name", d["name"] == "demo")
c("roundtrip nodes", len(d["nodes"]) == 2)
c("roundtrip edges", len(d["edges"]) == 1)

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
