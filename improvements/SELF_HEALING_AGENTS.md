# Self-Healing Agents

> Phase 21: Agents that detect failures, diagnose root causes, and auto-recover.
> Status: 🛠 Implementing | Priority: P0 | Effort: 14-21 days

---

## Architecture

```
Agent Run
  │
  ▼
┌──────────────────────────────────────────────┐
│         SelfHealingWrapper                    │
│                                              │
│  ┌────────────┐    ┌──────────────────┐      │
│  │ Tool Call  │───▶│ Try tool         │      │
│  │ Interceptor│    │ (with retry)     │      │
│  └────────────┘    └──────┬───────────┘      │
│                           │                   │
│                    ┌──────▼───────────┐       │
│                    │ Success?         │       │
│                    └──┬───────────┬───┘       │
│                  Yes  │           │  No       │
│               ┌───────▼┐   ┌──────▼──────┐   │
│               │ Return  │   │ Try fallback│   │
│               │ result  │   │ tools       │   │
│               └─────────┘   └──────┬──────┘   │
│                               No   │          │
│                           ┌────────▼──────┐   │
│                           │ All failed?   │   │
│                           └──┬──────────┬──┘   │
│                         Yes │          │ No   │
│                     ┌───────▼┐  ┌──────▼──┐   │
│                     │Escalate│  │ Return  │   │
│                     │(to LLM)│  │fallback │   │
│                     └────────┘  │ result  │   │
│                                 └─────────┘   │
└──────────────────────────────────────────────┘
```

## API Design

```python
from chainforge.core.healing import SelfHealingWrapper, HealingPolicy

# Policy: how to heal
policy = HealingPolicy(
    max_retries=2,
    retry_delay=0.5,
    fallback_tools={
        "web_search": ["web_fetch", "duckduckgo_search"],
        "calculate": ["math_tool"],
    },
    track_failures=True,
)

# Wrap any agent
healing_agent = SelfHealingWrapper(agent=my_agent, policy=policy)

# Use exactly like Agent
stream = await healing_agent.run("Search for AI news")
async for event in stream:
    print(event)

# Inspect stats
print(healing_agent.stats())
# {"total_calls": 42, "failures": 3, "healed": 2, "per_tool": {...}}
```

## HealingPolicy Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_retries` | int | 2 | Max retries per tool call |
| `retry_delay` | float | 0.5 | Seconds between retries |
| `fallback_tools` | dict | {} | Tool name → fallback tool names |
| `track_failures` | bool | True | Track per-tool success/failure rates |
| `auto_escalate` | bool | True | Send final error to LLM if all fallbacks fail |

## Error Classification

Tool errors are classified into:
- `tool_error`: Exception during tool execution
- `content_error`: Tool returned an error message in content (starts with "Error:")
- `timeout`: Tool took too long (not yet implemented)
- `llm_refusal`: LLM refused to respond (not yet implemented)

## Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `chainforge/core/healing.py` | HealingPolicy, SelfHealingWrapper, tool wrapping |
| 2 | `tests/test_healing.py` | Unit tests for healing logic |
| 3 | README update | Documentation |
