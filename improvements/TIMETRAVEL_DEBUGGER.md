# TimeTravelDebugger + Execution Provenance Graph + ALDP

> ChainForge's debugging stack: from checkpoint recording to real-time WebSocket debugging.

## Architecture

```
StepDebugger (CLI debug)
    |
    v
TimeTravelDebugger (record/replay/branch/diff)
    |
    v
Execution Provenance Graph (causal chain tracing)
    |
    v
ALDP — Agent Live Debug Protocol (WebSocket real-time debug)
```

## TimeTravelDebugger

Records full execution snapshots at each state transition.

**Key API:**
- `run(prompt, auto_checkpoint=True)` — execute with recording
- `replay(checkpoint_id)` — replay events from a checkpoint
- `branch(checkpoint_id)` — fork execution from a checkpoint
- `diff(id_a, id_b)` — compare two checkpoints
- `provenance_graph()` — build causal execution graph
- `trace_decision(content)` — trace why an output occurred
- `explain(content)` — human-readable explanation

**Internal:** `ExecutionCheckpoint` model with messages, context, events.

## Execution Provenance Graph

Each event records what caused it, building a causal DAG.

- `_infer_cause(event, index)` — backward causal inference
- `trace_decision(target, max_depth)` — walk causal chain
- `explain(target)` — formatted trace

## ALDP — Agent Live Debug Protocol

WebSocket-based protocol for real-time debugging, inspired by Chrome DevTools Protocol.

**Events (Server -> Client):** state, tool_call, tool_result, llm_response, paused, error, done
**Commands (Client -> Server):** pause, resume, step_over, get_state, set_breakpoint

**Implementation:** Zero extra dependencies — pure asyncio with RFC 6455 WebSocket.

## Usage

```python
from chainforge.core.time_travel import TimeTravelDebugger
from chainforge.core.agent_aldp import AldpDebugSession

# Post-hoc debugging
debugger = TimeTravelDebugger(agent)
stream = await debugger.run("Analyze")
trace = debugger.trace_decision("result")
print(debugger.explain("result"))

# Real-time debugging via WebSocket
session = AldpDebugSession(agent)
stream = await session.run("Analyze", aldp_port=9229)
# Connect: ws://localhost:9229
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Wrapper pattern (not middleware) | Need full event access including pre/post hooks |
| asyncio-based WebSocket | Zero extra dependencies, core ChainForge principle |
| JSON messages | Universal compatibility, easy to debug |
| Port 9229 | Matches Chrome DevTools convention |
| Pause via asyncio.Event | Non-blocking, composable with other async operations |
