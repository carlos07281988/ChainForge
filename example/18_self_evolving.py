"""example/18_self_evolving.py — SelfEvolvingAgent verification."""
import sys, asyncio
from chainforge.testing import MockLLM, MockResponse
from chainforge.agents.self_evolving import SelfEvolvingAgent, ExecutionMetrics
passed = 0; failed = 0

def check(n, ok):
    global passed, failed
    if ok: passed += 1; print(f"  \u2705 {n}")
    else: failed += 1; print(f"  \u274c {n}")

def test_evolving_create():
    e = SelfEvolvingAgent(
        llm=MockLLM(responses=[MockResponse(content="hi")]),
        system_prompt="You are helpful.",
        evolution_enabled=True,
        min_runs_for_evolution=3,
    )
    check("e1: evolution enabled", e.evolution_enabled == True)
    check("e2: min_runs", e.min_runs_for_evolution == 3)
    check("e3: system_prompt set", e.system_prompt == "You are helpful.")
    check("e4: run_count starts 0", e.run_count == 0)

def test_execution_metrics():
    m = ExecutionMetrics(prompt_length=50, tool_calls=3, tool_names=["search"], success=True)
    check("e5: prompt_length", m.prompt_length == 50)
    check("e6: tool_calls", m.tool_calls == 3)
    check("e7: tool_names", m.tool_names == ["search"])
    check("e8: success", m.success == True)
    check("e9: timestamp set", m.timestamp > 0)

def test_analyze_no_history():
    e = SelfEvolvingAgent(llm=MockLLM(), evolution_enabled=True, min_runs_for_evolution=3)
    imps = e._analyze_and_evolve()
    check("e10: no history = no improvements", len(imps) == 0)

def test_analyze_with_history():
    e = SelfEvolvingAgent(llm=MockLLM(), evolution_enabled=True, min_runs_for_evolution=2)
    for i in range(3):
        e._record_metrics(ExecutionMetrics(prompt_length=50, tool_names=["tool_a"] * (i + 1)))
    check("e11: run_count after 3", e.run_count == 3)
    imps = e._analyze_and_evolve()
    check("e12: has improvements", len(imps) > 0)
    check("e13: tool usage in improvements", any("tool" in i for i in imps))

def test_evolve_system_prompt():
    e = SelfEvolvingAgent(
        llm=MockLLM(),
        system_prompt="You are helpful.",
        evolution_enabled=True,
    )
    for i in range(3):
        e._record_metrics(ExecutionMetrics(prompt_length=50, success=True))
    imps = e._analyze_and_evolve()
    new_prompt = e._evolve_system_prompt(imps)
    check("e14: prompt evolved", new_prompt is not None)
    check("e15: prompt includes learnings", "Evolution" in new_prompt)

def test_evolve_no_history():
    e = SelfEvolvingAgent(llm=MockLLM(), system_prompt="Hi", evolution_enabled=True)
    new = e._evolve_system_prompt([])
    check("e16: no improvements = no change", new is None)

async def main():
    print("=" * 58)
    print("  SelfEvolvingAgent")
    print("=" * 58)
    test_evolving_create(); test_execution_metrics()
    test_analyze_no_history(); test_analyze_with_history()
    test_evolve_system_prompt(); test_evolve_no_history()
    print(f"\n  Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    asyncio.run(main())
