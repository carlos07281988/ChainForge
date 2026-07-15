"""example/06_core_state.py — Agent state machine verification."""
import sys
from chainforge.core.state import AgentState, StateTracker, StateTransition
from chainforge.core.state import ThreadInfo, InMemoryCheckpointer
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_states():
    for s in ["initializing", "thinking", "executing_tool", "observing", "responding", "error", "done"]:
        check(f"s1: {s}", AgentState(s).value == s)

def test_transition():
    t = StateTransition(to_state=AgentState.thinking)
    check("t1: to_state", t.to_state == AgentState.thinking)
    check("t2: from_state None", t.from_state is None)
    check("t3: iteration default 0", t.iteration == 0)
    check("t4: timestamp set", t.timestamp > 0)

def test_transition_with_meta():
    t = StateTransition(
        from_state=AgentState.thinking,
        to_state=AgentState.executing_tool,
        iteration=2, depth=1,
        tool_name="search", message="Searching...",
    )
    check("t5: from_state", t.from_state == AgentState.thinking)
    check("t6: iteration", t.iteration == 2)
    check("t7: depth", t.depth == 1)
    check("t8: tool_name", t.tool_name == "search")

def test_tracker_init():
    tr = StateTracker()
    check("tr1: init state", tr.current_state == AgentState.initializing)
    check("tr2: init iteration 0", tr.iteration == 0)
    check("tr3: history empty", len(tr.history) == 0)

def test_tracker_transition():
    tr = StateTracker()
    t = tr.transition(AgentState.thinking)
    check("tr4: transition state", tr.current_state == AgentState.thinking)
    check("tr5: history length 1", len(tr.history) == 1)
    check("tr6: history has entry", len(tr.history) == 1)
    check("tr7: returned transition", t.to_state == AgentState.thinking)

def test_tracker_multiple():
    tr = StateTracker()
    tr.transition(AgentState.thinking)
    tr.transition(AgentState.executing_tool, tool_name="calc")
    tr.transition(AgentState.observing)
    tr.transition(AgentState.responding)
    tr.transition(AgentState.done)
    check("tr8: final state done", tr.current_state == AgentState.done)
    check("tr9: history length 5", len(tr.history) == 5)
    check("tr10: history length", len(tr.history) == 5)

def test_thread_info():
    ti = ThreadInfo(thread_id="th1")
    check("ti1: thread_id", ti.thread_id == "th1")
    check("ti2: created_at set", ti.created_at > 0)
    check("ti3: checkpoint_count 0", ti.checkpoint_count == 0)

import asyncio
def test_checkpointer():
    cp = InMemoryCheckpointer()
    threads = asyncio.run(cp.list_threads())
    check("cp1: no threads", len(threads) == 0)

def main():
    print("=" * 58)
    print("  Core State \u2014 AgentState, StateTracker, transitions")
    print("=" * 58)
    test_states(); test_transition(); test_transition_with_meta()
    test_tracker_init(); test_tracker_transition(); test_tracker_multiple()
    test_thread_info(); test_checkpointer()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
