# Agent Callback System — Structured Observability Hooks

> 为 ChainForge Agent 提供生命周期级别的可观测性钩子

## Design

Callbacks are the **third pillar** of ChainForge's agent lifecycle system:

| Pillar | Purpose | Can Modify? |
|--------|---------|-------------|
| Middleware | Wraps the Stream | Yes |
| ReasoningStrategy | Hooks into loop | Yes (messages/response) |
| **Callback** | Observes and records | **No** (one-way) |

### Events

| Event | When | Useful For |
|-------|------|------------|
| `on_agent_start` | Agent run begins | Metrics, logging, tracing |
| `on_agent_end` | Agent run completes | Reporting, persistence |
| `on_llm_start` | Before LLM call | Token counting, latency |
| `on_llm_end` | After LLM response | Response analysis |
| `on_tool_start` | Before tool executes | Tool usage monitoring |
| `on_tool_end` | After tool completes | Result validation |
| `on_error` | Error occurs | Alerting, debugging |

### Usage

```python
from chainforge.callbacks import LoggingCallback, MetricsCallback

metrics = MetricsCallback()
agent = Agent(
    llm=llm,
    callbacks=[LoggingCallback(), metrics],
)

stream = await agent.run("Hello")
async for event in stream: ...

report = metrics.get_report()
print(f"LLM calls: {report['llm_calls']}")
print(f"Duration: {report['duration_s']}s")
```

### Custom Callback

```python
from chainforge.callbacks import BaseCallback

class MyCallback(BaseCallback):
    async def on_llm_start(self, messages, context=None):
        print(f"Sending {len(messages)} messages to LLM")
```

## Files

| File | Description |
|------|-------------|
| `chainforge/callbacks/__init__.py` | Exports |
| `chainforge/callbacks/base.py` | Callback protocol, BaseCallback |
| `chainforge/callbacks/logging.py` | LoggingCallback |
| `chainforge/callbacks/metrics.py` | MetricsCallback |
| `chainforge/core/agent.py` | Integration with Agent loop |
| `tests/test_callbacks.py` | Tests |
