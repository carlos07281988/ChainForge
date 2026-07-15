"""example/16_time_travel.py — TimeTravelDebugger verification."""
import sys, asyncio
from chainforge.core.time_travel import TimeTravelDebugger, ExecutionCheckpoint
from chainforge.core.agent import Agent
from chainforge.testing import MockLLM, MockResponse
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

async def test_debugger_create():
    llm = MockLLM(responses=[MockResponse(content="test")])
    agent = Agent(llm=llm)
    dbg = TimeTravelDebugger(agent=agent, max_checkpoints=10)
    check("t1: max_checkpoints=10", dbg._max_checkpoints == 10)

def test_checkpoint_creation():
    ckp = ExecutionCheckpoint(id="test_1", iteration=1, state="thinking")
    check("t2: checkpoint id", ckp.id == "test_1")
    check("t3: iteration set", ckp.iteration == 1)
    check("t4: state set", ckp.state == "thinking")
    check("t5: timestamp set", ckp.timestamp > 0)

def test_summary():
    dbg = TimeTravelDebugger(agent=Agent(llm=MockLLM()))
    s = dbg.summary()
    check("t6: summary has keys", "total_checkpoints" in s)
    check("t7: no checkpoints", s["total_checkpoints"] == 0)

def test_diff():
    dbg = TimeTravelDebugger(agent=Agent(llm=MockLLM()))
    a = ExecutionCheckpoint(id="a", iteration=1, state="thinking")
    b = ExecutionCheckpoint(id="b", iteration=5, state="done")
    dbg._checkpoints = {"a": a, "b": b}
    dbg._checkpoint_list = ["a", "b"]
    d = dbg.diff("a", "b")
    check("t8: iteration_delta", d["iteration_delta"] == 4)
    check("t9: state_a == thinking", d["state_a"] == "thinking")
    check("t10: state_b == done", d["state_b"] == "done")

def test_diff_invalid():
    dbg = TimeTravelDebugger(agent=Agent(llm=MockLLM()))
    try:
        dbg.diff("x", "y")
        check("t11: invalid diff raises error", False)
    except ValueError:
        check("t11: invalid diff raises ValueError", True)

def test_replay_invalid():
    dbg = TimeTravelDebugger(agent=Agent(llm=MockLLM()))
    try:
        dbg.replay("nonexistent")
        check("t12: invalid replay raises error", False)
    except ValueError:
        check("t12: invalid replay raises ValueError", True)

async def test_branch_invalid():
    dbg = TimeTravelDebugger(agent=Agent(llm=MockLLM()))
    try:
        stream = dbg.branch("nonexistent")
        events = await stream.collect()
        check("t13: invalid branch raises error", False)
    except ValueError:
        check("t13: invalid branch raises ValueError", True)

async def main():
    print("=" * 58)
    print("  TimeTravelDebugger")
    print("=" * 58)
    await test_debugger_create()
    test_checkpoint_creation()
    test_summary()
    test_diff()
    test_diff_invalid()
    test_replay_invalid()
    await test_branch_invalid()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
