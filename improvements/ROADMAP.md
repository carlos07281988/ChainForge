# ChainForge Roadmap

> 路线图：当前状态、短期计划、长期愿景

## Legend

| Icon | Meaning |
|------|---------|
| ✅ | Done |
| 🛠 | In progress |
| 📋 | Planned |
| 💡 | Future idea |

---

## Phase 1: Foundation ✅

- ✅ Core agent loop with streaming
- ✅ 5 LLM providers (OpenAI, Anthropic, Google, Azure, Bedrock)
- ✅ Tool system with `@tool` decorator
- ✅ Middleware chain (retry, rate_limit, timeout, tracing, logging, langfuse)
- ✅ Multi-agent orchestration (Swarm, Supervisor)
- ✅ DAG graph execution engine + visual editor
- ✅ Human-in-the-loop
- ✅ MCP client
- ✅ A2A protocol (Agent-to-Agent)
- ✅ Evaluation framework
- ✅ CLI scaffolding
- ✅ 10 agent patterns

## Phase 2: Production Ready 🛠 (Current)

### 🔥 Code Sandbox + Multi-modal

| State | Feature |
|-------|---------|
| 🛠 | Subprocess sandbox (safe Python code execution) |
| 📋 | Docker sandbox (full isolation) |
| 📋 | Built-in `@tool` for code execution |
| 📋 | Multi-modal Message parts (image, file, audio) |
| 📋 | File loader utilities |
| 📋 | Image input in providers |

### 🔥 Memory 2.0 (Vector Memory)

| State | Feature |
|-------|---------|
| 🛠 | Embedding function protocol |
| 🛠 | VectorMemory with semantic retrieval |
| 📋 | Hierarchical memory (working → episodic → semantic) |
| 📋 | Cross-session persistent memory |
| 📋 | Memory manager coordinating multiple backends |

### 🔥 Agent Config Declaration

| State | Feature |
|-------|---------|
| 🛠 | YAML/JSON agent config schema |
| 🛠 | Agent builder from config |
| 📋 | `chainforge init --from-config` |
| 📋 | Environment variable injection |
| 📋 | Template system |

## Phase 3: Advanced (📋 Planned)

| Feature | Description |
|---------|-------------|
| Guardrails | Input/output content safety, injection detection, tool permissions |
| Context Management | Context caching, sliding window, compression |
| Agent Inspector | Browser-based debugger (state, memory, tool calls) |
| Fleet Management | Agent worker pool, load balancing, health checks |
| Cross-Agent Tracing | Distributed trace across A2A boundaries |
| Agent Testing Suite | Mock LLM, simulation, regression testing |

## Phase 4: Ecosystem (💡 Future)

| Feature | Description |
|---------|-------------|
| Agent Template Market | Community-contributed agent templates |
| MCP Tool Registry | Discover and install MCP tools |
| Cloud Deploy | `chainforge deploy` to serverless/K8s |
| Voice Agent | TTS/STT integration |
| Collaborative Agents | Real-time shared workspace |

---

## How to prioritize

1. **Sandbox + Multi-modal** — 2025 Agent 的基本能力，缺了就感觉不完整
2. **Memory 2.0** — 语义记忆是复杂 Agent 的基础设施
3. **Agent Config** — 让 Agent 能被声明和管理，走向更广泛用户
