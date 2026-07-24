# Behavior Contract Runtime

> Phase 27: Runtime execution and enforcement of ASL behavior contracts.
> Status: 🛠 Implementing | Priority: P2 | Effort: 10-14 days

---

## Architecture

```
Agent Run
    │
    ▼
┌──────────────────────────────────────┐
│  ContractEnforcer                    │
│                                      │
│  Before each tool call:              │
│    SecurityContract.check(name)      │
│    → violation? → block / warn      │
│                                      │
│  After each event:                   │
│    PerformanceContract.check(cost)   │
│    → over budget? → warn / stop      │
│                                      │
│  After agent completes:              │
│    ContractReport.generate()         │
└──────────────────────────────────────┘
```

## API

```python
from chainforge.core.contracts import (
    ContractRegistry,
    SecurityContract,
    PerformanceContract,
    ContractEnforcer,
)

# Define contracts
contracts = ContractRegistry()
contracts.add(SecurityContract(
    name="no_delete",
    rule="disallow_tool",
    tool_pattern="delete",
    severity="error",
))
contracts.add(PerformanceContract(
    name="budget",
    rule="max_llm_calls",
    value=5,
    severity="warn",
))

# Wrap agent with enforcement
enforcer = ContractEnforcer(agent=my_agent, contracts=contracts)
stream = await enforcer.run("Hello")

# Check results
report = enforcer.report()
# {"violations": [], "contracts_checked": 2, "passed": True}
```

## Contract Types

| Contract | Rule | Description |
|----------|------|-------------|
| SecurityContract | disallow_tool | Block specific tools by name/pattern |
| SecurityContract | max_calls_per_tool | Limit calls to a specific tool |
| PerformanceContract | max_llm_calls | Max LLM calls per run |
| PerformanceContract | max_tool_calls | Max tool calls per run |
| PerformanceContract | max_cost | Max cost per run |
| BehaviorContract | custom | User-defined check function |

## Severity Levels

- `error`: Tool execution is blocked, violation recorded
- `warn`: Violation is recorded, execution continues
