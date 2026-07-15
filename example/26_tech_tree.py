"""example/26_tech_tree.py — Tech Tree verification."""
import sys
from chainforge.evolution.tech_tree import TechTree, default_tech_tree
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

t = TechTree()
t.add_node("a", "A", "first"); t.add_node("b", "B", "needs A", requires=["a"], required_count=3, required_tool="x")
c("2 nodes", len(t.nodes) == 2)
c("node a name", t.nodes["a"].name == "A")
t.record_usage("x")
c("usage tracked", t.usage_counts.get("x", 0) >= 1)
t.record_usage("x"); t.record_usage("x")
c("node b unlocked", t.nodes["b"].is_unlocked)

dt = default_tech_tree()
c("default tree", len(dt.nodes) >= 7)
for _ in range(15): dt.record_usage("search")
dt.check_unlocks()
c("progress", dt.progress() > 0)
c("plot", len(dt.plot()) > 20)
print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
