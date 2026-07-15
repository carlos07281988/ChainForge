"""example/28_behavior_test.py — Behavior Test verification."""
import sys, asyncio
from chainforge.testing.behavior import BehaviorTest, BehaviorTestRunner, ExpectedBehavior, BehaviorAssertion
from chainforge.testing import MockLLM, MockResponse
from chainforge.core.agent import Agent
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

llm = MockLLM(responses=[MockResponse(content="hello")])
agent = Agent(llm=llm)
runner = BehaviorTestRunner(agent)

t1 = BehaviorTest(prompt="hi", name="greeting")
r1 = asyncio.run(runner.run(t1))
c("test ran", r1 is not None)
c("name stored", r1.test.name == "greeting")

t2 = BehaviorTest(prompt="test", forbidden_tools=["delete"])
r2 = asyncio.run(runner.run(t2))
c("assertions", len(r2.assertions) >= 1)
found = any(a.type == "tool_not_called" for a in r2.assertions)
c("tool_not_called found", found)

s = runner.summary()
c("summary has total", s["total"] >= 2)
c("summary has pass_rate", "pass_rate" in s)

ba = BehaviorAssertion(type="tool_called", passed=True)
c("assertion model", ba.passed == True)

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
