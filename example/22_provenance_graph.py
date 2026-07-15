"""example/22_provenance_graph.py — Provenance Graph verification."""
import sys, asyncio
from chainforge.core.time_travel import TimeTravelDebugger, ExecutionCheckpoint
from chainforge.core.agent import Agent
from chainforge.testing import MockLLM, MockResponse
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

agent = Agent(llm=MockLLM(responses=[MockResponse(content="test")]))
dbg = TimeTravelDebugger(agent)
c("debugger created", True)

pg = dbg.provenance_graph()
c("provenance graph", "events" in pg)
c("empty provenance", pg["total_events"] == 0)

trace = dbg.trace_decision("test")
c("empty trace", len(trace) == 0)

dbg._events = [
    {"type":"state","content":"thinking","data":{}},
    {"type":"text","content":"I need to search","data":{}},
    {"type":"tool_call","content":"","data":{"name":"search"}},
    {"type":"tool_result","content":"results","data":{"name":"search"}},
    {"type":"text","content":"answer: 42","data":{}},
]
pg2 = dbg.provenance_graph()
c("events tracked", pg2["total_events"] == 5)

trace2 = dbg.trace_decision("42")
c("trace finds 42", len(trace2) >= 2)

exp = dbg.explain("42")
c("explain works", "Execution Trace" in exp)

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
