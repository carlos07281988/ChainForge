<div align="center">

```
        ________  __________   _____  _   ___________   _____  ___________
       / ____/ / / / ____/ /  / __ \/ | / / ____/   | / __ \/ ____/ ___/
      / /   / /_/ / /_  / /  / / / /  |/ / / __/ /| |/ / / / / __/ __ \
     / /___/ __  / __/ / /___/ /_/ / /|  / /_/ / ___ / /_/ / /_/ / /_/ /
     \____/_/ /_/_/   /_____/\____/_/ |_/\____/_/  |_\____/\____/_____/

```

</div>

# ChainForge

**锻造链** — *Craft your LLM call chains, tool chains, and processing chains.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-green)]()
[![Tests](https://img.shields.io/badge/tests-201%20passed-brightgreen)]()
[![Dependencies](https://img.shields.io/badge/dependencies-2-red)]()

> **ChainForge is what LangChain should have been if it were designed today.**  
> Minimal. Streaming-first. Type-safe. Async-native. Built for the post-LangChain era.

```bash
pip install chainforge
```

**Core Principles:** `protocol-based` · `streaming-first` · `async-native` · `type-safe` · `zero-overhead-abstractions`

<p align="right">
  <a href="README.md">🇬🇧 English</a> · <a href="README.zh.md">🇨🇳 中文</a>
</p>


---

## Why ChainForge? / 为什么选择 ChainForge

LangChain pioneered the agent framework space, but its architecture carries years of backward-compatibility debt. ChainForge is a clean-slate redesign driven by what we've learned since:

LangChain 开创了 Agent 框架的先河，但其架构背负着多年的向后兼容债务。ChainForge 是一次彻底的重构。

| Pain Point | LangChain | ChainForge | 对比说明 |
|---|---|---|---|
| API complexity | Chain, Runnable, LCEL | **Protocol-based** — minimal | API 复杂度降低 80% |
| Streaming | Bolted on, callbacks | **Streaming-first** | 流式原生支持 |
| Tool integration | Layered pipeline | **Tool Protocol** | 工具即插即用 |
| State management | Separate LangGraph | **Agent loop built-in** | 无需额外框架 |
| Observability | LangSmith external | **Built-in middleware** | 零外部依赖 |
| Async | Secondary | **Async-native** | 性能更优 |
| Error handling | Opaque traces | **Typed errors** | 精确定位 |
| Dependencies | 100+ transitive | **Only pydantic + stdlib** | 极致轻量 |

---

## Quick Start / 快速开始

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

## Installation / 安装

**Requires Python 3.11+ / 需要 Python 3.11+**

```bash
# Core — only pydantic + typing_extensions / 核心（仅 pydantic）
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

## Core Concepts / 核心概念

### Message / 消息
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

### Tool / 工具
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

### Agent / 代理
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

### Stream / 流
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

### Pipeline / 流水线
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

### Middleware / 中间件
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

## Examples / 示例

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

### Pipeline / 流水线 Composition

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

### Middleware / 中间件: Custom Logger

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

## Architecture / 架构

```
chainforge/
├── __init__.py          # Public API exports
├── __main__.py          # python -m chainforge
├── _version.py          # Version string
├── client.py            # HTTP client for ChainForge server
├── server.py            # HTTP server (FastAPI + REST + SSE)
├── logging.py           # Structured logging (text/json, per-module levels)
│
├── core/                # Foundational primitives
│   ├── __init__.py
│   ├── agent.py         # Agent execution loop (LLM ↔ Tools ↔ LLM...)
│   ├── llm.py           # LLM Protocol + LLMResponse
│   ├── tool.py          # Tool Protocol + FunctionTool + @tool decorator
│   ├── message.py       # Message, ToolCall, ToolResult, Role enum
│   ├── stream.py        # StreamEvent (7 types) + Stream wrapper
│   ├── pipeline.py      # Sequential step composition with >>
│   ├── graph.py         # DAG graph execution engine
│   ├── middleware.py    # Middleware chain — composable agent hooks
│   ├── state.py         # Agent state machine (StateTracker)
│   ├── structured_output.py  # Pydantic response_model parsing
│   ├── human_in_loop.py # Human approval/interrupt hooks
│   ├── utils.py         # Core utilities (run_sync)
│   └── errors.py        # Typed errors (ProviderError, ToolExecutionError, ...)
│
├── providers/           # LLM implementations
│   ├── __init__.py
│   ├── openai.py        # OpenAI — streaming, tool calls, token usage
│   ├── anthropic.py     # Anthropic — streaming, tool calls, token usage
│   ├── google.py        # Google Gemini — streaming, tool calls
│   ├── azure.py         # Azure OpenAI — streaming, tool calls
│   └── bedrock.py       # AWS Bedrock — Claude, Llama, Mistral, Titan
│
├── agents/              # 10 agent patterns
│   ├── __init__.py
│   ├── react.py         # ReAct (Thought/Action/Observation loop)
│   ├── plan_execute.py  # Plan → Execute → Synthesize
│   ├── reflection.py    # Generate → Critique → Improve
│   ├── self_ask.py      # Decompose → Answer → Synthesize
│   ├── tree_of_thoughts.py  # BFS multi-path reasoning
│   ├── chain_of_thought.py  # CoT + Self-Consistency
│   ├── conversational.py    # Multi-turn with auto-summary compression
│   ├── router.py        # Intent classification → route to specialist
│   ├── tool_agent.py    # Heavy tool orchestration agent
│   ├── agent_chain.py   # Sequential agent composition
│   ├── agent_tool.py    # Wrap agent as callable Tool
│   └── agent_hub.py     # Central registry + discovery + auto-routing
│
├── tools/               # Tool system
│   ├── __init__.py
│   └── builtin.py       # Built-in tools (current_time, calculate, echo)
│
├── skills/              # Reusable capability bundles
│   ├── __init__.py
│   ├── base.py          # Skill model + SkillTool wrapper
│   ├── loader.py        # SKILL.md file loader
│   └── registry.py      # SkillRegistry — register, search, discover
│
├── memory/              # Conversation memory
│   ├── __init__.py
│   ├── buffer.py        # Sliding-window buffer
│   └── summary.py       # Running-summary compression
│
├── middleware/           # Middleware implementations
│   ├── __init__.py
│   ├── logging_mw.py    # Structured logging middleware
│   ├── retry.py         # Retry with exponential backoff
│   ├── timeout.py       # Execution timeout guard
│   ├── rate_limit.py    # Token bucket rate limiter
│   ├── opentelemetry.py # OpenTelemetry tracing middleware
│   └── langfuse.py      # Langfuse observability middleware
│
├── orchestration/       # Multi-agent orchestration
│   ├── __init__.py
│   ├── supervisor.py    # Planner → delegate → synthesize
│   └── swarm.py         # Parallel / sequential / conference modes
│
├── eval/                # Evaluation & testing framework
│   ├── __init__.py
│   ├── case.py          # EvalCase — test prompts + expected behaviors
│   ├── metrics.py       # MetricsCollector — time, tokens, cost, success
│   ├── suite.py         # EvalSuite — collection + JSON load/save
│   ├── runner.py        # EvalRunner — execute suites against agents
│   └── report.py        # EvalReport — JSON / Markdown / HTML / Text
│
├── tracing/             # Observability
│   ├── __init__.py
│   └── tracer.py        # Tracer, Span, ConsoleTracer, tracing_middleware
│
├── mcp/                 # Model Context Protocol
│   ├── __init__.py
│   └── client.py        # MCPClient — dynamic tool discovery (stdio/SSE)
│
├── cli/                 # CLI interface
│   └── __init__.py      # init, quickstart, skill, serve, run, eval
│
├── examples/            # Runnable examples
│   ├── basic_agent.py   # Weather + search agent demo
│   └── memory_example.py  # Multi-turn conversation with memory
│
└── tests/               # 210+ tests
```

### Execution Flow / 执行流程

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

## API Reference / API 参考

### `chainforge`

| `Middleware` | Composable hook wrapper |

### `chainforge.core.errors`

| `MaxIterationsError` | Agent exceeded max iterations |

### `chainforge.providers`

| `AnthropicProvider(model, api_key, max_tokens)` | `anthropic>=0.30` |

### `chainforge.agents`

| `ToolAgent` | High-level tool orchestration agent |

### `chainforge.tracing`

| `Trace` | Complete trace containing spans |

### `chainforge.memory`

| `SummaryMemory(max_recent)` | Running summary + recent messages |

### `chainforge.mcp`

| `MCPServer` | MCP server configuration (stdio/SSE) |

---

## Design Principles / 设计原则

1. **Protocols, not base classes** — interfaces are `typing.Protocol` subclasses. You don't inherit, you implement.
2. **Streaming is the default** — every execution returns `Stream`. Non-streaming is just `await stream.collect_text()`.
3. **Minimal core, extensible edges** — core depends on `pydantic` + stdlib. Features are optional (providers, tracing, MCP).
4. **Type-safe everywhere** — Pydantic v2 for all structured data. Schemas are generated, never hand-written.
5. **Async-first, sync-available** — async is primary, but `Pipeline.__call__()` and `Tool.__call__()` work synchronously.
6. **Composability over configuration** — Pipeline `>>`, middleware chains, tool lists. Composition is the API.

---

## Roadmap / 路线图

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
- [x] **Agent evaluation & testing framework** — `chainforge eval` CLI, `EvalSuite`/`EvalRunner`/`EvalReport` API
- [x] **Streaming agent state visualization** — real-time web dashboard with SSE agent state visualization
- [x] **Graph-based agent visual editor** — interactive DAG editor with drag-and-drop, export, run
- [x] **A2A protocol** — Agent-to-Agent (Google A2A) standardized agent communication
  - AgentCard advertisement, task lifecycle management, SSE streaming

---

## Logging / 日志

ChainForge provides a structured, production-ready logging system built on Python's `logging` module.

### Quick Start / 快速开始

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

### Logging / 日志 Middleware

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

---

## Skills / 技能

Skills are reusable capability bundles — instructions + optional tools — that agents can load, compose, and invoke. Compatible with Codex SKILL.md format.

### Using Skills

```python
from chainforge.skills import Skill, SkillRegistry

# Create a skill inline
greeting_skill = Skill(
    name="greeter",
    description="Creates enthusiastic greetings",
    instructions="""
You are a greeting specialist. Always use an enthusiastic tone
and include emojis.
""",
)

# Load from SKILL.md (Codex-compatible format)
skill = Skill.load("./skills/my-skill/SKILL.md")

# Compose into an agent
agent = Agent(
    llm=llm,
    tools=[...],
    skills=[greeting_skill, skill],
)
```

### SKILL.md Format

ChainForge loads skills from standard Codex SKILL.md files:

```markdown
---
name: my-skill
description: What this skill does
tags: [tag1, tag2]
---

## Instructions

Markdown instructions here...
```

### Skill Registry

```python
from chainforge.skills import SkillRegistry

registry = SkillRegistry()
registry.load_dir("./skills")
registry.register(my_skill)

# Query
skill = registry.get("skill-name")
results = registry.search("weather")
tagged = registry.find_by_tag("demo")

# Convert all skills to tools
tools = registry.to_tools()
```

### Skills / 技能 as Tools

Each skill automatically generates a tool specification, enabling agents to discover and invoke skills dynamically:

```python
skill_tool = skill.to_tool()
# The agent can now call this skill via tool calls
```

### CLI

```bash
chainforge skill list        # List available skills
chainforge skill add <path>  # Register a skill
chainforge skill info <name> # Show skill details
```

---

## Agent Patterns / 代理模式

ChainForge ships with **10 agent patterns** covering reasoning, multi-step execution, quality enhancement, conversation, and routing. Each pattern produces the standard `Stream` event type, so they work interchangeably with middleware, logging, and tracing.

---

### 1. Agent (Base) / 基础代理

**功能.** The foundational execution loop: send messages + tool schemas to the LLM, execute any tool calls returned, append results, and repeat until a text response is produced. All other patterns build on this core.

**适用场景.** Any task where an LLM needs tool access. Default choice — start here and switch to a specialized pattern only when you need specific reasoning behavior.

**Example: Knowledge Q&A with search**

```python
from chainforge import Agent, tool
from chainforge.providers import OpenAIProvider

@tool
def search(query: str) -> str:
    """Search a knowledge base."""
    db = {"chainforge": "A next-gen agent framework."}
    return db.get(query.lower(), f"No results for: {query}")

async def main():
    agent = Agent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[search],
        system_prompt="You are a helpful assistant.",
    )
    async for event in await agent.run("What is ChainForge?"):
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `llm`, `tools`, `system_prompt`, `max_iterations` (default 10), `temperature`, `parallel_tool_calls` (default True).

---

### 2. ReActAgent / 反应代理

**功能.** The agent follows an explicit Thought -> Action -> Observation loop. It reasons about the situation (Thought), calls a tool (Action), reviews the result (Observation), and repeats until it can answer. The reasoning trace is preserved for debugging.

**适用场景.** Tasks that benefit from visible step-by-step reasoning: research questions, troubleshooting, analysis that requires justification.

**流程:** `thought -> action (tool call) -> observation -> thought -> ... -> response`

**Example: Multi-step research**

```python
from chainforge import tool
from chainforge.providers import OpenAIProvider
from chainforge.agents import ReActAgent

@tool
def search_facts(topic: str) -> str:
    """Search for factual information."""
    return f"Key facts about {topic}: [data from knowledge base]"

async def main():
    agent = ReActAgent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[search_facts],
        verbose=True,  # prints thought/action/observation steps
    )
    stream = await agent.run("What was the GDP growth rate in 2023?")
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `verbose` (print reasoning trace), `max_iterations` (default 15).

---

### 3. PlanAndExecute / 规划执行

**功能.** Three-phase execution:
1. **Plan** - LLM analyzes the task and produces a numbered step-by-step plan
2. **Execute** - each step runs through its own mini-Agent with full tool access
3. **Synthesize** - LLM combines step results into a coherent final answer

**适用场景.** Tasks requiring multiple distinct sub-operations: market research reports, data analysis pipelines, content creation workflows. Excels when each step depends on the previous one's output.

**流程:** `planning -> executing (step 1, step 2, ...) -> synthesizing -> done`

**状态事件:** `planning`, `executing`, `synthesizing`, `done`

**Example: Market research report**

```python
from chainforge import tool
from chainforge.providers import OpenAIProvider
from chainforge.agents import PlanAndExecute

@tool
def search_market(segment: str) -> str:
    """Search market data for a segment."""
    return f"Market data for {segment}: size=10B, growth=15%"

async def main():
    agent = PlanAndExecute(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[search_market],
        max_plan_steps=5,
    )
    stream = await agent.run("Research the AI chip market and provide forecasts")
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `max_plan_steps`, `max_iterations` (per-step), `temperature`.

---

### 4. Reflection / 反思代理

**功能.** Three-phase quality cycle that repeats N times:
1. **Generate** - produces an initial answer (with tool access)
2. **Critique** - self-evaluates the answer for accuracy, completeness, clarity
3. **Improve** - generates an improved version addressing all critique points

**适用场景.** Quality-critical content where accuracy matters: code review, essay writing, contract analysis. Each round typically improves quality, diminishing after 2-3 rounds.

**流程:** `generating -> critiquing -> improving -> [critiquing -> improving ...] -> done`

**状态事件:** `generating`, `critiquing`, `improving`, `done`

**Example: Code review and improvement**

```python
from chainforge.providers import OpenAIProvider
from chainforge.agents import Reflection

async def main():
    agent = Reflection(
        llm=OpenAIProvider(model="gpt-4o"),
        reflection_rounds=2,  # two critique-improve cycles
    )
    stream = await agent.run("Write a Python function to merge two sorted lists")
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)
        elif event.type == "state":
            print(f"\n--- [{event.data['state']}] ---\n")

asyncio.run(main())
```

**关键参数:** `reflection_rounds` (default 1), `max_iterations`.

---

### 5. SelfAsk / 自问代理

**功能.** Three-phase decomposition:
1. **Decompose** - LLM breaks the main question into 2-5 concrete sub-questions
2. **Answer Each** - each sub-question gets its own Agent with full tool access
3. **Synthesize** - LLM combines sub-answers into a comprehensive final answer

**适用场景.** Multi-faceted questions that benefit from divide-and-conquer: comparisons ("Python vs Rust"), impact analysis ("How will AI affect healthcare?"), complex evaluations.

**流程:** `decomposing -> answering (Q1, Q2, ...) -> synthesizing -> done`

**状态事件:** `decomposing`, `answering`, `synthesizing`, `done`

**Example: Technology comparison**

```python
from chainforge import tool
from chainforge.providers import OpenAIProvider
from chainforge.agents import SelfAsk

@tool
def search_tech(topic: str) -> str:
    """Search technical documentation."""
    return f"Data about {topic}: [documentation results]"

async def main():
    agent = SelfAsk(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[search_tech],
    )
    stream = await agent.run("Compare Python and Rust for building a web API")
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `max_sub_questions` (default 5), `max_iterations`.

---

### 6. TreeOfThoughts / 思维树

**功能.** BFS-based multi-path reasoning:
1. Start with the problem as root node
2. At each depth level, generate N candidate thoughts from each existing path
3. Score each candidate (1-10) for promise, coherence, and progress
4. Keep only the top-K (breadth) candidates for the next level
5. After reaching depth D, select the highest-scoring path overall
6. Optionally refine the answer with tools

**适用场景.** Problems with multiple valid reasoning directions: mathematical proofs, logic puzzles, strategic planning. One wrong turn early can derail single-path agents, but ToT explores alternatives. More expensive than single-path (N x K x D LLM calls).

**流程:** `initializing -> exploring (depth 1, 2, 3) -> selecting -> done`

**状态事件:** `initializing`, `exploring`, `selecting`, `done`

**Example: Logic puzzle solving**

```python
from chainforge.providers import OpenAIProvider
from chainforge.agents import TreeOfThoughts

async def main():
    agent = TreeOfThoughts(
        llm=OpenAIProvider(model="gpt-4o"),
        candidates_per_step=3,  # N = 3 thoughts per node
        breadth=2,              # K = keep top 2 per level
        depth=3,                # D = 3 levels deep
        temperature=0.7,
    )
    stream = await agent.run(
        "Three friends -- Alice, Bob, Carol -- each have a different favorite "
        "color: red, blue, green. Alice doesn't like blue. Bob's favorite is "
        "not green. Carol's favorite is red. What is each person's favorite?"
    )
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `candidates_per_step` (3-5), `breadth` (2-3), `depth` (2-4), `temperature`.

---

### 7. ChainOfThought / 思维链

**功能.** Generates N independent reasoning paths with Self-Consistency aggregation:
1. **Reason** - N parallel CoT paths, each with slightly varied temperature for diversity
2. **Aggregate** - analyzes all paths, identifies consensus, resolves contradictions
3. **Output** - produces a single answer reflecting the most reliable reasoning

**适用场景.** Tasks where answer reliability is paramount: factual questions, medical/legal analysis, compliance checks. Self-consistency reduces hallucination risk by cross-referencing multiple reasoning trajectories.

**流程:** `reasoning (path 1, 2, 3) -> aggregating -> done`

**状态事件:** `reasoning`, `aggregating`, `done`

**Example: High-reliability fact checking**

```python
from chainforge import tool
from chainforge.providers import OpenAIProvider
from chainforge.agents import ChainOfThought

@tool
def check_fact(claim: str) -> str:
    """Verify a factual claim."""
    return f"Evidence for '{claim}': [verified from sources]"

async def main():
    agent = ChainOfThought(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[check_fact],
        num_paths=3,       # 3 independent reasoning paths
        aggregate="vote",  # 'vote' for consensus, 'compare' for best-of-N
    )
    stream = await agent.run(
        "What is the current world population and is it growing or declining?"
    )
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `num_paths` (default 3), `aggregate` ("vote" or "compare").

---

### 8. ConversationalAgent / 对话代理

**功能.** Multi-turn agent with automatic context management:
- Maintains a sliding window of recent turns (BufferMemory)
- Maintains a running summary of older turns (SummaryMemory)
- When the window fills, automatically compresses old history into a summary
- Preserves full fidelity for recent N turns while keeping long-term context

**适用场景.** Any multi-turn interaction: chatbots, virtual assistants, interactive tutoring, customer support. Handles sessions of 50+ turns gracefully.

**Flow per turn:** `thinking -> [tool calls] -> done` (with auto-summary on overflow)

**Example: Customer support bot**

```python
import asyncio
from chainforge import tool
from chainforge.providers import OpenAIProvider
from chainforge.agents import ConversationalAgent

@tool
def lookup_order(order_id: str) -> str:
    """Look up an order by ID."""
    return f"Order {order_id}: status=shipped, delivery_date=2026-07-15"

async def main():
    agent = ConversationalAgent(
        llm=OpenAIProvider(model="gpt-4o-mini"),
        tools=[lookup_order],
        system_prompt="You are a helpful customer support agent.",
        max_turns_before_summary=6,
    )

    # Turn 1
    async for event in await agent.run("Hi, I need help with my order"):
        if event.type == "text":
            print(event.content, end="", flush=True)

    # Turn 2 - remembers context
    async for event in await agent.run("My order ID is ORD-12345"):
        if event.type == "text":
            print(event.content, end="", flush=True)

    # Turn 3 - still remembers the order ID
    async for event in await agent.run("Can you cancel it?"):
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `max_turns_before_summary`, `system_prompt`, `max_iterations`.

**Method:** `agent.clear_history()` resets conversation.

---

### 9. RouterAgent / 路由代理

**功能.** Two-phase intelligent routing:
1. **Classify** - a fast classifier LLM identifies the user's intent from available route names
2. **Route** - forwards the full request to the matched specialized agent

Each route can have its own LLM, tools, system prompt, and even agent pattern.

**适用场景.** Systems serving multiple domains: a smart assistant that handles weather, coding, search, and calculations through specialized backends.

**流程:** `classifying -> routing -> [delegated agent execution] -> done`

**状态事件:** `classifying`, `routing`, `done`

**Example: Multi-domain smart assistant**

```python
from chainforge import Agent
from chainforge.providers import OpenAIProvider
from chainforge.agents import RouterAgent

weather_agent = Agent(
    llm=OpenAIProvider(model="gpt-4o-mini"),
    system_prompt="You are a weather specialist.",
)
code_agent = Agent(
    llm=OpenAIProvider(model="gpt-4o"),
    system_prompt="You are a coding expert. Provide runnable code.",
)
search_agent = Agent(
    llm=OpenAIProvider(model="gpt-4o-mini"),
    system_prompt="You are a research assistant.",
)

async def main():
    router = RouterAgent(
        classifier_llm=OpenAIProvider(model="gpt-4o-mini"),
        routes={
            "weather": weather_agent,
            "coding": code_agent,
            "search": search_agent,
        },
        default_route="search",
    )

    for query in [
        "What is the weather in Tokyo?",
        "Write a Python quick sort",
        "Who won the 2022 World Cup?",
    ]:
        print(f"\nQ: {query}")
        stream = await router.run(query)
        async for event in stream:
            if event.type == "text" and event.content:
                print(event.content[:120], "...")
            if event.type == "state" and event.data.get("state") == "routing":
                print(f"  [routed to: {event.data.get('route', '?')}]")

asyncio.run(main())
```

**关键参数:** `classifier_llm` (fast model), `routes` (name to agent dict), `default_route`.

---

### 10. ToolAgent / 工具代理

**功能.** Heavy tool orchestration agent. Automatically analyzes the user's request, determines which tools to call and in what order, and chains them together to accomplish complex tasks.

**适用场景.** Tasks involving multiple tools where orchestration logic is non-trivial: data ETL pipelines, multi-API workflows, automated reporting.

**Example: Automated data pipeline**

```python
from chainforge import tool
from chainforge.providers import OpenAIProvider
from chainforge.agents import ToolAgent

@tool
def extract_data(source: str) -> str:
    """Extract data from a source."""
    return f"Raw data from {source}: [1000 rows]"

@tool
def transform_data(data: str, rules: str) -> str:
    """Transform data according to rules."""
    return f"Transformed using rules: {rules}"

@tool
def load_data(data: str, destination: str) -> str:
    """Load data to destination."""
    return f"Loaded to {destination}"

async def main():
    agent = ToolAgent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[extract_data, transform_data, load_data],
    )
    stream = await agent.run(
        "Extract sales data from PostgreSQL, clean it, and load to Snowflake"
    )
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

**关键参数:** `max_iterations` (default 20).

---

### Quick Selection Guide / 快速选择指南

| "Automate a data pipeline" | **ToolAgent** | Tool orchestration |



## Reasoning Strategies / 推理策略

Reasoning Strategies are a **framework-level abstraction** that lets you inject structured thinking patterns into any Agent's execution loop — without modifying the Agent itself.

Unlike the pre-built agent patterns (ReAct, ChainOfThought, etc.) in `chainforge/agents/`, reasoning strategies are **composable hooks** that can be mixed and matched on any Agent.

### Architecture / 架构

Each strategy implements one or more hooks called at different points in the Agent loop:

| Hook | When Called | Return | Use Case |
|------|------------|--------|----------|
| `before_llm` | Before each LLM call | (messages, context) | Inject instructions, add context |
| `after_llm` | After each LLM response | (response, messages, context) | Self-critique, verify output |
| `on_tool_result` | After a tool executes | (result, messages, context) | Validate tool output |
| `should_stop` | End of each iteration | bool | Early stopping based on quality |

### Built-in Strategies / 内置策略

#### ChainOfThought — Step-by-Step Reasoning

Injects a "think step by step" instruction before each LLM call.

```python
from chainforge.reasoning import ChainOfThought

agent = Agent(llm=llm, reasoning=[ChainOfThought()])
# The LLM will be prompted to reason step by step before answering
```

Customizable prompt:

```python
cot = ChainOfThought(prompt="Let me work through this carefully before answering.")
```

#### ReasoningSteps — Explicit Sub-Step Planning

Breaks down the user's request into numbered steps before execution.

```python
from chainforge.reasoning import ReasoningSteps

agent = Agent(llm=llm, reasoning=[ReasoningSteps(max_steps=5)])
# On first iteration, asks LLM to plan steps. Executes them one by one,
# stops after max_steps iterations.
```

#### SelfReflection — Self-Critique and Improvement

After generating a response, asks the LLM to review its own answer and produce a refined version.

```python
from chainforge.reasoning import SelfReflection

agent = Agent(llm=llm, reasoning=[SelfReflection()])
# Flow: LLM responds -> reflection prompt -> LLM revises -> final answer
```

#### Verification — Double-Check Before Final

Prompts the LLM to verify its answer for factual accuracy, logical consistency, and completeness before finalizing.

```python
from chainforge.reasoning import Verification

agent = Agent(llm=llm, reasoning=[Verification()])
# Flow: LLM responds -> verification prompt -> LLM corrects -> final answer
```

### Combining Strategies / 组合使用

Strategies compose naturally. They run in order for each hook:

```python
agent = Agent(llm=llm, reasoning=[
    ChainOfThought(),     # 1. Think step by step
    SelfReflection(),     # 2. Self-critique output
    Verification(),       # 3. Double-check final
])
```

### Custom Strategy / 自定义策略

Subclass `ReasoningStrategy` and override the hooks you need:

```python
from chainforge.reasoning import ReasoningStrategy

class FactCheckStrategy(ReasoningStrategy):
    async def after_llm(self, response, messages, context):
        if not response.content:
            return response, messages, context
        messages.append(Message.system(
            "Fact-check the above response. List any inaccuracies."
        ))
        response.content = None
        return response, messages, context

agent = Agent(llm=llm, reasoning=[FactCheckStrategy()])
```

### Why Strategies, Not Patterns? / 策略 vs 模式

| Aspect | Agent Patterns (agents/) | Reasoning Strategies (reasoning/) |
|--------|------------------------|----------------------------------|
| Approach | Pre-built Agent subclasses | Composable hooks on any Agent |
| Flexibility | Fixed behavior, choose one | Mix and match, stack multiple |
| Reuse | Low, self-contained | High, small and focused |
| Integration | Agent is replaced | Agent is enhanced |

In short: **patterns are recipes, strategies are ingredients.**

## Agent Linking / 代理链接

ChainForge provides three mechanisms for connecting agents: **AgentTool** (agent as callable), **AgentChain** (sequential composition), and **AgentHub** (registry + discovery).

These enable hierarchical agent systems, multi-step workflows, and dynamic agent selection.

---

### Agent / 代理Tool — Agent as a Tool / Agent 工具化

Wrap any Agent into a Tool that other agents can call. This enables **hierarchical agent systems**: a high-level agent delegates sub-tasks to specialized agents.

```python
from chainforge import Agent
from chainforge.providers import OpenAIProvider
from chainforge.agents import AgentTool

# Create a specialized agent
search_agent = Agent(
    llm=OpenAIProvider(model="gpt-4o-mini"),
    tools=[],
    system_prompt="You are a web search specialist.",
)

# Wrap it as a Tool
search_tool = AgentTool(
    search_agent,
    name="web_search",
    description="Search the web for information",
)

# Another specialized agent
calc_agent = Agent(
    llm=OpenAIProvider(model="gpt-4o"),
    system_prompt="You are a calculation specialist.",
)
calc_tool = AgentTool(calc_agent, name="calculator", description="Perform calculations")

# Main agent uses specialized agents as tools
main_agent = Agent(
    llm=OpenAIProvider(model="gpt-4o"),
    tools=[search_tool, calc_tool],
    system_prompt="Delegate to specialists when needed.",
)
```

**流程:** Main agent receives a task -> decides to call `web_search` -> `search_agent` runs as sub-agent -> returns text result -> main agent continues.

**关键参数:** `agent` (any agent), `name`, `description`, `timeout_seconds`.

---

### Agent / 代理Chain — Sequential Agent Composition / 顺序代理链

Chain agents in sequence, where each agent receives the previous agent's output as context. The Agent version of Pipeline, purpose-built for agents.

```python
from chainforge import Agent
from chainforge.providers import OpenAIProvider
from chainforge.agents import AgentChain

# Define individual agents
researcher = Agent(
    llm=OpenAIProvider(model="gpt-4o"),
    system_prompt="You are a thorough researcher. Gather detailed information.",
)
analyzer = Agent(
    llm=OpenAIProvider(model="gpt-4o"),
    system_prompt="You are a data analyst. Analyze and extract insights.",
)
writer = Agent(
    llm=OpenAIProvider(model="gpt-4o-mini"),
    system_prompt="You are a report writer. Write clear, concise reports.",
)

# Compose them
chain = AgentChain(name="research_pipeline")
chain.add_step("research", researcher, "Researches the topic")
chain.add_step("analyze", analyzer, "Analyzes findings")
chain.add_step("write", writer, "Writes final report")

# Execute the chain
stream = await chain.run("Impact of AI on healthcare in 2026")
async for event in stream:
    if event.type == "state":
        print(f"[{event.data['state']}] {event.data.get('step', '')}")
    elif event.type == "text":
        print(event.content, end="", flush=True)
```

**流程:** `chain_start -> step_start (research) -> step_done -> step_start (analyze) -> step_done -> step_start (write) -> step_done -> chain_done`

**状态事件:** `chain_start`, `step_start`, `step_done`, `chain_done`

**Nesting:** AgentChain can itself be wrapped as a Tool via `.to_tool()`:

```python
research_tool = chain.to_tool("research_pipeline", "Full research pipeline")
main_agent = Agent(llm=llm, tools=[research_tool, other_tools])
```

---

### Agent / 代理Hub — Registry + Discovery + Auto-Routing / 注册中心

Central registry for managing agents at scale. Register agents with metadata, search/discover them, and auto-generate routers.

```python
from chainforge import Agent
from chainforge.providers import OpenAIProvider
from chainforge.agents import AgentHub

hub = AgentHub()

# Register agents with metadata
hub.register("weather", weather_agent, "Weather forecasts", tags=["info", "public"])
hub.register("coding", code_agent, "Code generation and review", tags=["dev", "private"])
hub.register("search", search_agent, "Web search", tags=["info", "public"])
hub.register("data", data_agent, "Data analysis", tags=["analytics"])

# Discover
all_agents = hub.list()
public_agents = hub.find_by_tag("public")
matching = hub.search("code")

# Auto-create a router from all registered agents
router = hub.create_router(
    classifier_llm=OpenAIProvider(model="gpt-4o-mini"),
    default_route="search",
)
stream = await router.run("Write a Python function")  # routes to "coding" agent

# Create a chain from selected agents
chain = hub.create_chain(["search", "data"], name="research_analyze")
```

**方法:**
- `register(name, agent, description, tags)` — register with metadata
- `get(name)` — retrieve an agent
- `list()` — list all with metadata
- `search(query)` — search by name/description
- `find_by_tag(tag)` — filter by tag
- `create_router(classifier_llm)` — auto-generate RouterAgent
- `create_chain(step_names)` — auto-generate AgentChain
- `summary()` — human-readable overview

---

### Linking Patterns Summary / 链接模式总结

| **AgentHub** | Registry + discovery | Managing many agents, auto-routing |


## Evaluation & Testing / 评估测试

ChainForge includes a built-in evaluation framework for benchmarking agent performance against test cases.

### Quick Start / 快速开始

```python
from chainforge.eval import EvalCase, EvalSuite, EvalRunner, format_report

# Define test cases
cases = [
    EvalCase(
        name="greeting",
        prompt="Say hello!",
        expected_contains=["hello", "Hello"],
        tags=["basic"],
    ),
    EvalCase(
        name="tool_use",
        prompt="What is the weather in Beijing?",
        expected_tool="get_weather",
        tags=["tools"],
    ),
]

# Create a suite
suite = EvalSuite(name="demo", cases=cases)

# Run evaluation
runner = EvalRunner(agent, suite, name="my_agent")
result = await runner.run_all()

# Print report
print(format_report(result, fmt="text"))
```

### CLI / 命令行

```bash
# Run evaluation on a registered agent
chainforge eval my_agent

# Run specific test cases only
chainforge eval my_agent --cases greeting

# Load test suite from a JSON file
chainforge eval my_agent --suite test_suite.json

# Export report as HTML or JSON
chainforge eval my_agent --format html --output report.html
```

### Test Case Configuration / 测试用例配置

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique test case name |
| `prompt` | `str` | Input prompt for the agent |
| `expected` | `list[ExpectedBehavior]` | Behavior checks (contains, tool_called, no_errors, json_valid, custom) |
| `expected_contains` | `list[str]` | Strings that should appear in output |
| `expected_tool` | `str \| None` | Tool the agent should have called |
| `context` | `dict \| None` | Optional context data |
| `tags` | `list[str]` | Tags for filtering |
| `weight` | `float` | Weight for scoring (default 1.0) |
| `custom_check` | `str \| None` | Python expression with `output` and `events` vars |

### Metrics Collected / 收集的指标

| Metric | Description |
|--------|-------------|
| `response_time` | Total time in seconds |
| `tool_call_count` | Number of tool calls made |
| `iterations` | Agent loop iterations |
| `response_length` | Length of final text response |
| `success` | Whether agent completed without errors |
| `token_count` | Estimated token usage |
| `cost` | Estimated cost in USD |

### Report Formats / 报告格式

```python
# Plain text (default)
text_report = format_report(result, fmt="text")

# Markdown (great for PR descriptions)
md_report = format_report(result, fmt="markdown")

# HTML (standalone, shareable)
html_report = format_report(result, fmt="html")

# JSON (machine-readable)
json_report = format_report(result, fmt="json")

# Save to file
format_report(result, fmt="html", path="eval_report.html")
```

### HTTP API / HTTP API 端点

```bash
curl -X POST http://localhost:8000/api/v1/eval/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "cases": [
      {"name": "test1", "prompt": "Hello", "expected": ["no_errors"]}
    ]
  }'
```

---

## Dashboard / 控制台

ChainForge provides a web dashboard for real-time agent streaming visualization and DAG editing.

### Starting the Dashboard / 启动

```bash
# Install server dependencies
pip install "chainforge[server]"

# Start with agents
chainforge serve --port 8000

# Open browser to http://localhost:8000/dashboard
```

### Dashboard Pages / 页面

| Page | URL | Description |
|------|-----|-------------|
| **Overview** | `/dashboard` | Registered agents list, server status, quick actions |
| **Agent Run** | `/dashboard/agent-run` | Real-time streaming visualization with state machine |
| **DAG Editor** | `/dashboard/dag-editor` | Interactive graph-based pipeline editor |

### API Endpoints / API 端点

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agents` | List all registered agents |
| GET | `/api/v1/agents/{id}` | Agent details and tools |
| POST | `/api/v1/agents/{id}/run` | Run agent, returns JSON |
| GET | `/api/v1/agents/{id}/run/stream` | Run agent, SSE streaming |
| POST | `/api/v1/eval/run` | Run evaluation tests |
| GET | `/api/v1/dag/stream` | Execute DAG via SSE |
| GET | `/api/v1/health` | Health check |

---

## DAG Visual Editor / DAG 可视化编辑器

The DAG (Directed Acyclic Graph) editor lets you visually construct and execute agent pipelines.

### Features / 功能

- **Drag-and-drop** — Move nodes freely on the canvas
- **Visual connections** — Click output port → input port to create edges
- **Node types** — Step, Input, Output, Router, Merge
- **JSON export** — Export your DAG as JSON for reuse
- **Live execution** — Run the DAG and see results in real-time via SSE

### Node Types / 节点类型

| Type | Purpose | Example |
|------|---------|---------|
| **Input** | Entry point, accepts initial data | `"Hello DAG"` |
| **Step** | Processing step with function | Double input, transform text |
| **Router** | Conditional branching | Route based on value |
| **Merge** | Combine multiple inputs | Concatenate results |
| **Output** | Terminal node, final result | Return processed data |

### Programmatic DAG / 编程式 DAG

```python
from chainforge import DAG

dag = DAG(name="pipeline")
dag.add_node("double", fn=lambda x: x * 2)
dag.add_node("add_one", fn=lambda x: x + 1)
dag.add_edge("double", "add_one")

stream = dag.run(21)
async for event in stream:
    if event.type == "text":
        print(event.content)  # 42
```

### DAG API / 执行 API

You can also execute DAGs programmatically via the API:

```bash
curl "http://localhost:8000/api/v1/dag/stream?dag=\
  {\"name\":\"test\",\"nodes\":[{\"id\":\"n1\",\"type\":\"step\"}],\"edges\":[]}"
```

---


---


---

## A2A Protocol / Agent-to-Agent 协议

ChainForge implements the [Google A2A protocol](https://github.com/google/A2A), enabling standardized communication between agents via HTTP JSON-RPC.

### Usage / 使用

```bash
# Start server with A2A endpoints
chainforge serve --a2a --port 8000
```

```python
from chainforge.a2a import (
    A2AClient, A2AAgentProxy,
    A2ARouter, create_a2a_app, mount_a2a,
)

# Client: discover and call remote agents
client = A2AClient()
card = await client.get_agent_card("http://remote:8000/a2a")
result = await client.send_task(
    "http://remote:8000/a2a",
    "task-1", "Weather in Beijing?",
)

# Proxy: treat remote agent as local
proxy = A2AAgentProxy("http://remote:8000/a2a")
output = await proxy.run("What's the weather?")

# Server: expose agents with A2A
app, router = create_a2a_app({"agent": my_agent})

# Or mount into existing FastAPI app
mount_a2a(existing_app, agents={"agent": my_agent})
```

### Protocol Endpoints / 协议端点

| Method | Path | Description |
|--------|------|-------------|
| GET | `/a2a/agent-card` | Get agent's advertised capabilities |
| POST | `/a2a/task-send` | Send a task to the agent |
| POST | `/a2a/task-get` | Query current task state |
| POST | `/a2a/task-cancel` | Cancel a running task |
| POST | `/a2a/task-subscribe` | SSE stream task updates |
| POST | `/a2a/task-resubscribe` | Replay completed task history |

### Core Models / 核心模型

| Type | Description |
|------|-------------|
| `AgentCard` | Agent identity — name, capabilities, skills |
| `Task` | Work unit with state machine lifecycle |
| `TaskState` | `submitted → working → completed / failed / canceled` |
| `Message` | Communication payload — role + parts (text/file/data) |
| `Artifact` | Output produced during task execution |
| `Skill` | Advertised capability with metadata |

### Architecture / 架构

```mermaid
sequenceDiagram
    participant Client
    participant A2A_Server
    participant Agent
    
    Client->>A2A_Server: GET /agent-card
    A2A_Server-->>Client: AgentCard (skills, capabilities)
    
    Client->>A2A_Server: POST /task-send {id, message}
    A2A_Server->>Agent: execute_task()
    A2A_Server-->>Client: Task (state=submitted/working)
    
    loop Poll
        Client->>A2A_Server: POST /task-get {id}
        A2A_Server-->>Client: Task (state update)
    end
    
    Client->>A2A_Server: POST /task-subscribe {id, message}
    A2A_Server->>Agent: execute_task()
    A2A_Server-->>Client: SSE: task_update / task_complete
```




## Code Sandbox / 代码沙箱

ChainForge provides isolated code execution environments for agents — safe Python and shell execution without host system exposure.

### Usage / 使用

```python
from chainforge.sandbox import SubprocessSandbox

sandbox = SubprocessSandbox(timeout=30)
result = await sandbox.execute("print('hello world')", "python")
print(result.stdout)   # hello world
print(result.exit_code)  # 0

# Or via built-in agent tools
from chainforge.tools.builtin import execute_python, execute_bash
# Agent automatically picks them up:
# agent = Agent(llm=llm, tools=[execute_python, execute_bash])
```

### Sandbox Implementations / 实现

| Implementation | Isolation | When to Use |
|---|---|---|
| `SubprocessSandbox` | Process-level | Development, testing |
| `DockerSandbox` | Container-level | Production *(planned)* |

### Multi-modal File Loading / 多模态文件加载

```python
from chainforge.core.files import FileLoader, load_file, load_image

loader = FileLoader()
fc = loader.load("chart.png")
print(fc.is_image)  # True
print(fc.mime_type)  # image/png
print(load_image("photo.jpg"))  # data:image/jpeg;base64,...

csv_data = loader.load_csv("data.csv")  # list of dicts
json_data = loader.load_json("config.json")
```


## Memory 2.0 (Vector Memory) / 向量记忆

Beyond sliding-window buffer memory, ChainForge now supports **semantic retrieval memory** with vector embeddings.

### Three-Level Memory / 三层记忆

| Level | Type | Purpose |
|-------|------|---------|
| **Working** | `BufferMemory` | Recent context (full fidelity, sliding window) |
| **Episodic** | `VectorMemory` | Past sessions (semantic similarity retrieval) |
| **Semantic** | `VectorMemory` | Facts, preferences, knowledge |

### Usage / 使用

```python
from chainforge.memory import VectorMemory, MemoryManager, IdentityEmbedding

# Standalone vector memory
mem = VectorMemory()
await mem.add("User prefers dark mode", {"type": "preference"})
await mem.add("User knows Python 3.12", {"type": "knowledge"})
results = await mem.query("What language?")
for r in results:
    print(r["text"], r["score"])

# Memory manager (all three levels)
from chainforge.memory.buffer import BufferMemory
manager = MemoryManager(
    working=BufferMemory(max_messages=20),
    episodic=VectorMemory(),
    semantic=VectorMemory(),
)
await manager.store("User likes async Python", {"role": "user"})
context = await manager.get_context("What does the user like?")
```

### Embedding Providers / 嵌入支持

| Provider | Type | API Key Needed |
|----------|------|----------------|
| `IdentityEmbedding` | Hash-based (dev/test) | No |
| OpenAI | `text-embedding-3-small` | Yes *(planned)* |


## Agent Config Declaration / 声明式 Agent 配置

Define agents declaratively with YAML or JSON — no Python code required.

### Example / 示例

```yaml
# agent.yaml
name: research-assistant
llm:
  provider: openai
  model: gpt-4o
  temperature: 0.3
tools:
  - name: calculate
    type: builtin
  - name: execute_python
    type: builtin
memory:
  type: vector
system_prompt: "You are a research assistant."
```

```bash
# Validate and show config
chainforge config agent.yaml --show

# Start server with config
chainforge serve --config agent.yaml --port 8000
```

### Usage / 使用

```python
from chainforge.config.loader import load_agent_config
from chainforge.config.builder import build_agent_from_config

# Load from file (supports ${ENV_VAR} injection)
config = load_agent_config("agent.yaml")
agent = build_agent_from_config(config)

# Or from dict
config = load_agent_config_from_dict({
    "llm": {"provider": "openai", "model": "gpt-4o"},
    "tools": [{"name": "calculate", "type": "builtin"}],
})
agent = build_agent_from_config(config)

async for event in await agent.run("What is 2 + 2?"):
    if event.type == "text":
        print(event.content, end="")
```

### Config Schema / 配置结构

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `"agent"` | Agent name |
| `llm.provider` | string | required | `openai`, `anthropic`, `google`, `azure`, `bedrock` |
| `llm.model` | string | `"gpt-4o"` | Model name |
| `tools[].name` | string | — | Tool name |
| `tools[].type` | string | `"builtin"` | `builtin`, `mcp`, `skill`, `python` |
| `memory.type` | string | — | `buffer`, `summary`, `vector` |
| `system_prompt` | string | — | System instructions |
| `max_iterations` | int | `10` | Max tool-use iterations |

## License / 许可

Apache 2.0

---

<p align="center"><strong>锻造链</strong> — 锻造你的链。</p>
