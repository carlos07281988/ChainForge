# ChainForge

**锻造链** — 把你的 LLM 调用链、工具链、处理链"锻造"出来。

A next-generation agent framework. Minimal, streaming-first, type-safe, and built for the post-LangChain era.

```text
pip install chainforge
```

```text
ChainForge is what LangChain should have been if it were designed today.
```

---

## Why ChainForge?

LangChain pioneered the agent framework space, but its architecture carries years of backward-compatibility debt. ChainForge is a clean-slate redesign driven by what we've learned since:

| Pain Point | LangChain | ChainForge |
|---|---|---|
| API complexity | Chain, Runnable, LCEL, runnable graph... pick your abstraction | **Protocol-based** — minimal interfaces via Python `typing.Protocol` |
| Streaming | Bolted on, callbacks needed | **Streaming-first** — `Stream` is the default return type everywhere |
| Tool integration | `@tool` decorator is clean, but execution pipeline is layered | **Tool Protocol** — `Tool` is a first-class citizen from day one |
| State management | Separate LangGraph framework | **Agent loop built-in**, Pipeline with `>>` composition |
| Observability | LangSmith as external service, callbacks are complex | **Built-in middleware** — `ConsoleTracer` in 3 lines, no external dependency |
| Async | Supported but secondary | **Async-native** — sync is a thin convenience wrapper |
| Error handling | Opaque, long stack traces | **Typed errors** (`ProviderError`, `ToolExecutionError`, `MaxIterationsError`) |
| Dependencies | 100+ transitive deps | **Core: just `pydantic` + stdlib** |
| Type safety | Partial (pydantic v1, optional) | **Pydantic v2** everywhere — every message, tool spec, and event is typed |

---

## Quick Start

```python
import asyncio
from chainforge import Agent
from chainforge.providers import OpenAIProvider
from chainforge.tools import tool


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city."""
    temperatures = {"beijing": 28, "tokyo": 22, "london": 15, "new york": 26}
    temp = temperatures.get(city.lower(), 20)
    if unit == "fahrenheit":
        temp = temp * 9 / 5 + 32
    return f"{city.title()}: {temp:.0f}°{'C' if unit == 'celsius' else 'F'}, Sunny"


async def main():
    agent = Agent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[get_weather],
        system_prompt="You are a helpful weather assistant.",
        temperature=0.3,
    )

    stream = await agent.run("What's the weather in Beijing and Tokyo?")

    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)
        elif event.type == "tool_call":
            print(f"\n🔧 Calling {event.data['name']}({event.data['args']})")
        elif event.type == "tool_result":
            print(f"   Result: {event.data['content'][:60]}")
        elif event.type == "error":
            print(f"\n❌ Error: {event.content}")


asyncio.run(main())
```

---

## Installation

```bash
# Core — only pydantic + typing_extensions
pip install chainforge

# With OpenAI provider
pip install "chainforge[openai]"

# With Anthropic provider
pip install "chainforge[anthropic]"

# All providers
pip install "chainforge[all]"
```

**Requires Python 3.11+.**

---

## Core Concepts

### Message
A conversation message with typed roles (`system`, `user`, `assistant`, `tool`). Supports tool calls and tool results natively.

```python
from chainforge import Message

msgs = [
    Message.system("You are a helpful assistant."),
    Message.user("What is the weather in Beijing?"),
    Message.assistant(
        content="",
        tool_calls=[ToolCall(id="call_1", name="get_weather", args={"city": "Beijing"})],
    ),
    Message.tool_result("call_1", "get_weather", "Sunny, 28°C"),
]
```

### Tool
Any callable that provides a JSON Schema spec and implements `run(**kwargs) -> str`. The `@tool` decorator auto-generates the schema from type hints.

```python
from chainforge import tool

@tool
def search(query: str, limit: int = 10) -> str:
    """Search for information."""
    return f"Results for '{query}': ..."

# Auto-generated spec:
search.spec.name        # "search"
search.spec.description  # "Search for information."
search.spec.parameters   # {"type": "object", "properties": {...}, "required": ["query"]}
```

### Agent
The core execution loop: send messages + tool schemas to the LLM → execute tool calls → repeat until a text response is returned.

```python
agent = Agent(
    llm=OpenAIProvider(),
    tools=[get_weather, search],
    max_iterations=15,     # prevent infinite loops
    temperature=0.3,
    max_tokens=4096,
)
```

### Stream
Every agent execution returns a `Stream` of typed `StreamEvent` objects. Events include `text`, `tool_call`, `tool_result`, `error`, `done`, and `status`.

```python
stream = await agent.run("Hello")
async for event in stream:
    match event.type:
        case "text":       print(event.content)        # str
        case "tool_call":  print(event.data)            # {"name", "args", "id"}
        case "tool_result": print(event.data)           # {"name", "content", "is_error"}
        case "done":       print("Complete!")
        case "error":      print(f"Failed: {event.content}")
```

### Pipeline
A linear sequence of processing steps, composable with `>>`. Think of it as a simpler, more predictable alternative to LCEL.

```python
from chainforge import Pipeline

extract = lambda text: [x.strip() for x in text.split(",")]
translate = lambda items: [f"[CN] {i}" for i in items]
format_result = "\n".join

pipe = Pipeline(name="process", steps=[extract, translate, format_result])

# Execute
result = await pipe.run("hello,world,chainforge")
# Or synchronously:
result = pipe("hello,world,chainforge")

# Compose
pipe2 = pipe >> (lambda x: x.upper())
```

### Middleware
Composable hooks that wrap agent execution for cross-cutting concerns like tracing, rate limiting, retry, or logging.

```python
from chainforge import Agent
from chainforge.tracing import ConsoleTracer, tracing_middleware

tracer = ConsoleTracer()
agent = Agent(
    llm=...,
    tools=[...],
    middlewares=[tracing_middleware(tracer)],
)

# Every execution is now traced with timing and events
```

---

## Examples

### With Anthropic

```python
from chainforge import Agent
from chainforge.providers import AnthropicProvider

agent = Agent(
    llm=AnthropicProvider(model="claude-sonnet-4-20250514"),
    tools=[my_tool],
)
```

### ReAct Agent (thought/action/observation)

```python
from chainforge.agents import ReActAgent

agent = ReActAgent(
    llm=OpenAIProvider(model="gpt-4o"),
    tools=[search, calculate],
    verbose=True,           # prints reasoning steps
)
```

### Conversation Memory

```python
from chainforge import Agent
from chainforge.memory import BufferMemory

memory = BufferMemory(max_messages=50)

async def chat(prompt: str):
    # Load history, add new message
    history = await memory.load()
    from chainforge import Message
    messages = history + [Message.user(prompt)]

    stream = await agent.run(messages)
    response = ""
    async for event in stream:
        if event.type == "text":
            response += event.content
            print(event.content, end="", flush=True)

    # Save to memory
    await memory.save([Message.user(prompt), Message.assistant(response)])
```

### Pipeline Composition

```python
from chainforge import Pipeline

# Define processing steps
def clean(text: str) -> str:
    return text.strip().lower()

def tokenize(text: str) -> list[str]:
    return text.split()

def count_tokens(tokens: list[str]) -> int:
    return len(tokens)

# Compose pipeline
processing = Pipeline("analyze", steps=[clean, tokenize, count_tokens])

# Compose with >>
from chainforge.tools import tool

@tool
def analyze(text: str) -> str:
    """Analyze text complexity."""
    result = processing(text)
    return f"Token count: {result}"

print(processing("Hello World!  "))  # 2
```

### Middleware: Custom Logger

```python
from collections.abc import AsyncIterator
from chainforge.core.stream import StreamEvent
from chainforge.core.message import Message

async def logging_middleware(
    messages: list[Message],
    ctx: dict,
    next_handler,
) -> AsyncIterator[StreamEvent]:
    print(f"[LOG] Input: {len(messages)} messages")
    async for event in next_handler(messages, ctx):
        print(f"[LOG] Event: {event.type}")
        yield event
    print("[LOG] Done")

agent = Agent(
    llm=...,
    middlewares=[logging_middleware],
)
```

### MCP Tool Discovery

```python
from chainforge.mcp import MCPClient, MCPServer

client = MCPClient()
await client.connect(MCPServer(
    name="fs",
    command="npx @anthropic/mcp-filesystem",
    transport="stdio",
))

mcp_tools = await client.list_tools()
agent = Agent(llm=..., tools=mcp_tools)
```

---

## Architecture

```
chainforge/
│
├── core/                 # Foundational primitives
│   ├── agent.py          # Agent execution loop (LLM ↔ Tools ↔ LLM...)
│   ├── llm.py            # LLM Protocol + LLMResponse
│   ├── tool.py           # Tool Protocol + FunctionTool + @tool decorator
│   ├── message.py        # Message, ToolCall, ToolResult, Role enum
│   ├── stream.py         # StreamEvent (6 types) + Stream wrapper
│   ├── pipeline.py       # Sequential step composition with >>
│   ├── middleware.py     # Middleware chain — composable agent hooks
│   └── errors.py         # Typed errors (ProviderError, ToolExecutionError, ...)
│
├── providers/            # LLM implementations
│   ├── openai.py         # OpenAI — streaming, tool calls, token usage
│   └── anthropic.py      # Anthropic — streaming, tool calls, token usage
│
├── agents/               # Agent specializations
│   ├── react.py          # ReAct (Thought/Action/Observation loop)
│   └── tool_agent.py     # General tool orchestration agent
│
├── tools/                # Tool system
│   └── builtin.py        # Built-in tools (current_time, calculate, echo)
│
├── memory/               # Conversation memory
│   ├── buffer.py         # Sliding-window buffer
│   └── summary.py        # Running-summary compression
│
├── tracing/              # Observability
│   └── tracer.py         # Tracer, Span, ConsoleTracer, tracing_middleware
│
├── mcp/                  # Model Context Protocol
│   └── client.py         # MCPClient — dynamic tool discovery (stdio/SSE)
│
├── examples/             # Runnable examples
│   ├── basic_agent.py    # Weather + search agent demo
│   └── memory_example.py # Multi-turn conversation with memory
│
└── tests/                # 51 tests, 100% pass rate
```

### Execution Flow

```
User Prompt
     │
     ▼
┌─────────────────┐
│  Agent.run()     │
│  ┌─────────────┐ │
│  │ LLM.generate │ │─── Tool schemas ────► LLM provider
│  └──────┬──────┘ │
│         │        │
│    ┌────▼────┐   │
│    │ Tool     │   │─── Tool calls ─────► Execute tools
│    │ calls?   │   │
│    └────┬────┘   │
│     Yes │  No    │
│         ▼  ▼     │
│    ┌────┐ ┌────┐ │
│    │Run │ │Done│ │
│    │tool│ │    │ │
│    └────┘ └────┘ │
│         │        │
└─────────┴────────┘
          │
          ▼
     Stream of events
```

---

## API Reference

### `chainforge`

| Symbol | Description |
|---|---|
| `Agent` | Core agent with LLM + Tools execution loop |
| `Pipeline` | Sequential processing step composition |
| `Message` | Typed conversation message (system/user/assistant/tool) |
| `ToolCall` | Tool invocation request from the LLM |
| `ToolResult` | Result of executing a tool call |
| `Stream` | Async iterator over `StreamEvent` objects |
| `StreamEvent` | Typed event: `text`, `tool_call`, `tool_result`, `error`, `done`, `status` |
| `LLM` | Protocol for LLM providers |
| `LLMResponse` | Structured response from an LLM |
| `Tool` | Protocol for callable tools |
| `tool()` | Decorator that wraps a function into a `Tool` |
| `Middleware` | Composable hook wrapper |

### `chainforge.core.errors`

| Error | Description |
|---|---|
| `ChainForgeError` | Base error for all framework exceptions |
| `ProviderError` | LLM provider returned an error |
| `ToolExecutionError` | A tool raised during execution |
| `ConfigurationError` | Invalid configuration |
| `MaxIterationsError` | Agent exceeded max iterations |

### `chainforge.providers`

| Provider | Dependencies |
|---|---|
| `OpenAIProvider(model, api_key, base_url)` | `openai>=1.40` |
| `AnthropicProvider(model, api_key, max_tokens)` | `anthropic>=0.30` |

### `chainforge.agents`

| Agent | Description |
|---|---|
| `ReActAgent` | Structured Thought/Action/Observation loop |
| `ToolAgent` | High-level tool orchestration agent |

### `chainforge.tracing`

| Symbol | Description |
|---|---|
| `Tracer` | In-memory trace/span recorder |
| `ConsoleTracer` | Real-time span printing with timings |
| `tracing_middleware(tracer)` | Middleware factory for agent tracing |
| `Span` | A single operation span with timing |
| `Trace` | Complete trace containing spans |

### `chainforge.memory`

| Memory | Description |
|---|---|
| `BufferMemory(max_messages)` | Sliding window of recent messages |
| `SummaryMemory(max_recent)` | Running summary + recent messages |

### `chainforge.mcp`

| Symbol | Description |
|---|---|
| `MCPClient` | Client for MCP server tool discovery |
| `MCPServer` | MCP server configuration (stdio/SSE) |

---

## Design Principles

1. **Protocols, not base classes** — interfaces are `typing.Protocol` subclasses. You don't inherit, you implement.
2. **Streaming is the default** — every execution returns `Stream`. Non-streaming is just `await stream.collect_text()`.
3. **Minimal core, extensible edges** — core depends on `pydantic` + stdlib. Features are optional (providers, tracing, MCP).
4. **Type-safe everywhere** — Pydantic v2 for all structured data. Schemas are generated, never hand-written.
5. **Async-first, sync-available** — async is primary, but `Pipeline.__call__()` and `Tool.__call__()` work synchronously.
6. **Composability over configuration** — Pipeline `>>`, middleware chains, tool lists. Composition is the API.

---

## Roadmap

- [x] Core protocols and agent loop
- [x] OpenAI / Anthropic / Google / Azure / Bedrock providers
- [x] Tool system with `@tool` decorator
- [x] Middleware chain
- [x] Built-in tracing (ConsoleTracer, OpenTelemetry, Langfuse)
- [x] Pipeline composition + DAG graph execution
- [x] MCP client
- [x] Conversation memory (buffer + summary)
- [x] Multi-agent orchestration (Swarm / Supervisor)
- [x] Structured output / response_model
- [x] Rate limiting / retry / timeout middleware
- [x] Human-in-the-loop
- [x] Parallel tool execution
- [x] **Streaming agent state** — explicit state machine (StateTracker) with iteration/depth metadata
- [x] **Langfuse integration** — `langfuse_tracing_middleware`
- [x] **Bedrock provider** — AWS Bedrock (Claude, Llama, etc.)
- [x] **CLI scaffolding** — `chainforge init` / `quickstart`
- [ ] Streaming agent state visualization (dashboard/UI)
- [ ] Graph-based agent visual editor
- [ ] Agent evaluation & testing framework


---

## Logging

ChainForge provides a structured, production-ready logging system built on Python's `logging` module.

### Quick Start

```python
from chainforge import configure_logging

# Human-readable text output (default)
configure_logging(level="INFO")

# JSON structured logging (for log aggregators)
configure_logging(level="DEBUG", format="json")

# Per-module log levels
configure_logging(
    level="WARNING",
    module_levels={
        "agent": "DEBUG",         # Verbose agent internals
        "providers.openai": "INFO", # Show API calls
    },
)

# Log to file
configure_logging(level="DEBUG", output="logs/chainforge.log")
```

### Logging Middleware

The `logging_middleware` captures the full lifecycle of each agent run:

```python
from chainforge import Agent
from chainforge.middleware.logging_mw import logging_middleware

agent = Agent(
    llm=...,
    tools=[...],
    middlewares=[logging_middleware(
        log_input=True,         # Log user prompts
        log_output=True,        # Log agent responses
        log_tool_calls=True,    # Log tool invocations + results
        log_states=True,        # Log state transitions
    )],
)
```

Example JSON output:

```json
{"ts": "14:30:01.234", "level": "INFO", "logger": "chainforge.agent", "msg": "[run_123] Agent started", "data": {"input": "Weather in Beijing?", "messages": 2}}
{"ts": "14:30:01.456", "level": "DEBUG", "logger": "chainforge.agent", "msg": "[run_123] state → thinking", "data": {"state": {"state": "thinking", "iteration": 0}}}
{"ts": "14:30:02.001", "level": "INFO", "logger": "chainforge.agent", "msg": "[run_123] tool → get_weather", "data": {"tool_call": {"name": "get_weather", "args": {"city": "Beijing"}}}}
{"ts": "14:30:02.234", "level": "INFO", "logger": "chainforge.agent", "msg": "[run_123] Done in 1.20s", "data": {"duration_s": 1.2, "tool_calls": 1}}
```

### Module Loggers

Every module has a namespaced logger under `chainforge.*`:

| Logger | Module | Typical Level |
|---|---|---|
| `chainforge.agent` | Agent execution loop | INFO |
| `chainforge.providers.openai` | OpenAI API calls | DEBUG |
| `chainforge.providers.anthropic` | Anthropic API calls | DEBUG |
| `chainforge.middleware.retry` | Retry attempts | INFO |

### Structured Data

Use `log_data()` to attach structured data to log entries:

```python
from chainforge import log_data, get_logger

logger = get_logger("my_module")
log_data(logger, "INFO", "Processing complete", data={
    "items_processed": 42,
    "duration_ms": 150,
})
```

In JSON mode, the data dict appears under the `"data"` key. In text mode, it's appended to the message.
