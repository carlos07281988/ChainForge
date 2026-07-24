# SmartRouter 2.0 — Adaptive Multi-Model Router

> Phase 26: Route sub-tasks to the best model based on capability, cost, and latency.
> Status: 🛠 Implementing | Priority: P1 | Effort: 10-14 days

---

## Architecture

```
User Prompt
    │
    ▼
┌──────────────────────────────────────┐
│  AdaptiveRouter                       │
│                                      │
│  1. Task Classification              │
│     - complexity (1-5)               │
│     - required capabilities          │
│     - estimated cost budget          │
│                                      │
│  2. Model Selection                  │
│     - capability match ✅            │
│     - cost optimization 💰           │
│     - latency constraints ⚡          │
│     - current load 📊                │
│                                      │
│  3. Execution + Tracking             │
│     - run with selected model        │
│     - track cost & latency           │
│     - fallback on failure            │
└──────────────────────────────────────┘
    │
    ▼
Selected LLM (gpt-4o / claude / gemini / ...)
```

## API

```python
from chainforge.routing.adaptive import AdaptiveRouter, ModelRegistry, CostTracker

# Register models with capabilities, costs, latency
registry = ModelRegistry()
registry.register("gpt-4o", cost_per_1k=0.01, latency_ms=500,
                  capabilities={"chat", "tool_calling", "vision", "reasoning"})
registry.register("gpt-4o-mini", cost_per_1k=0.001, latency_ms=200,
                  capabilities={"chat", "tool_calling"})

# Adaptive router with cost-latency optimization
router = AdaptiveRouter(registry=registry, optimize_for="cost")
provider = await router.select("Explain quantum computing")
# Returns gpt-4o (needs reasoning capability)

provider = await router.select("What's 2+2?")
# Returns gpt-4o-mini (simple, cheap)

# Cost tracking
print(router.cost_tracker.summary())
```
