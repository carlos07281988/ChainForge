"""example/29_budget.py — Performance Budget verification."""
import sys
from chainforge.middleware.budget import PerformanceContract, BudgetTracker, budget_middleware
p=0;f2=0
def c(n,o):
    global p,f2
    if o: p+=1; print(f"  \u2705 {n}")
    else: f2+=1; print(f"  \u274c {n}")

ct = PerformanceContract(max_tool_calls=3, max_llm_calls=5)
c("contract tool limit", ct.max_tool_calls == 3)
c("contract llm limit", ct.max_llm_calls == 5)
c("forbidden_tools default", ct.forbidden_tools == [])

t = BudgetTracker()
c("budget ok", t.check(ct))
t.tool_calls = 4
c("tool exceeded", not t.check(ct))
c("exceeded field", t.exceeded == "max_tool_calls")

t2 = BudgetTracker()
t2.llm_calls = 10
c("llm exceeded", not t2.check(ct))

t3 = BudgetTracker()
t3.total_cost = 5.0
ct2 = PerformanceContract(max_cost_usd=1.0)
c("cost exceeded", not t3.check(ct2))

mw = budget_middleware(ct)
c("mw created", callable(mw))

print(f"\n  Results: {p} passed, {f2} failed")
sys.exit(0 if f2==0 else 1)
