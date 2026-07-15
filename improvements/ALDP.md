# Agent Live Debug Protocol (ALDP)

> WebSocket-based debugging protocol for agents, inspired by Chrome DevTools Protocol (CDP).

## Architecture

```
+-------------------------+     WebSocket (JSON)     +----------------------+
|  Agent Running           | <----------------------> |  Debug Client        |
|                          |   Events ->              |  (Terminal / UI)    |
|  AldpDebugSession        |   <- Commands            |                      |
|                          |                          |  pause / step       |
|  (wraps Agent.run())     |                          |  resume / breakpoint|
+-------------------------+                          +----------------------+
```

## Protocol Messages

### Events (Server -> Client)
- `state` — state transition with iteration metadata
- `tool_call` — tool invocation with name and args
- `tool_result` — tool execution result
- `llm_response` — LLM text output
- `paused` — execution paused at breakpoint
- `resumed` — execution continued
- `error` — execution error
- `done` — execution complete

### Commands (Client -> Server)
- `pause` — pause after current step
- `resume` — continue execution
- `step_over` — execute one step then pause
- `get_state` — request current execution state
- `set_breakpoint` — pause on specific event type
- `remove_breakpoint` — remove a breakpoint

## Files
- `aldp/protocol.py` — Event/Command type definitions + JSON serialization
- `aldp/server.py` — WebSocket server (zero extra dependencies, pure asyncio)
- `chainforge/core/agent_aldp.py` — Agent wrapper emitting ALDP events

## Usage

```python
from chainforge.aldp.server import ALDPServer
from chainforge.core.agent_aldp import AldpDebugSession

session = AldpDebugSession(agent)
stream = await session.run("Hello", aldp_port=9229)
# Connect via WebSocket to ws://localhost:9229
```
