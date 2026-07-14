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

### 🔥 Guardrails (Input/Output Safety)

| State | Feature |
|-------|---------|
| ✅ | InjectionDetector — prompt injection & jailbreak detection |
| ✅ | TopicFilter — allow/block topic restrictions |
| ✅ | PIILeakGuard — prevent sensitive data leakage in outputs |
| ✅ | ContentSafetyGuard — detect harmful content |
| ✅ | ToolPermissionPolicy — allow/block/dangerous tool lists |
| ✅ | QualityGuard — basic output quality checks |
| ✅ | GuardrailMiddleware — integrate into Agent pipeline |

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

### Agent Inspector

| State | Feature |
|-------|---------|
| ✅ | AgentInspector — collects agent execution events |
| ✅ | REST API + SSE for querying agent state |
| ✅ | Middleware integration for auto-recording |
| 📋 | Dashboard UI with state visualization |

### Fleet Management

| State | Feature |
|-------|---------|
| ✅ | Worker — wraps agent for concurrent execution |
| ✅ | WorkerPool — register, run, unregister agents |
| ✅ | TaskQueue — priority heap scheduling |
| 📋 | Auto-scaling worker pool |
| 📋 | Health checks and worker recovery |

### Cross-Agent Tracing

| State | Feature |
|-------|---------|
| ✅ | TraceContext — W3C trace context implementation |
| ✅ | inject_headers / extract_headers for A2A |
| ✅ | Child span creation for distributed traces |
| 📋 | Integration with A2A Router |
| 📋 | Trace visualization in dashboard |

### Agent Testing Suite

| State | Feature |
|-------|---------|
| ✅ | MockLLM — predefined responses, tool call simulation |
| ✅ | mock_agent() — create Agent + MockLLM for testing |
| ✅ | Assertion helpers (assert_called, assert_last_prompt_contains) |
| 📋 | Simulation environments (timeout, error scenarios) |
| 📋 | Regression diff testing |

### Context Management

| State | Feature |
|-------|---------|
| ✅ | SlidingWindowStrategy — token-aware conversation truncation |
| ✅ | CompressorStrategy — LLM-based context summarization |
| ✅ | TokenBudget — per-message-type token allocation |
| ✅ | Token estimation utilities |
| 📋 | Selective strategy — keep semantically relevant history |

### | Description |
|---------|-------------|
| Guardrails | Input/output content safety, injection detection, tool permissions |
| Context Management | Context caching, sliding window, compression |
| Agent Inspector | Browser-based debugger (state, memory, tool calls) |
| Fleet Management | Agent worker pool, load balancing, health checks |
| Cross-Agent Tracing | Distributed trace across A2A boundaries |
| Agent Testing Suite | Mock LLM, simulation, regression testing |

## Phase 4: LangChain Feature Parity (✅ Complete)

### Output Parsers (chainforge/parsers/)

| State | Feature |
|-------|---------|
| ✅ | JSONOutputParser — extract JSON from LLM responses |
| ✅ | PydanticOutputParser — parse into Pydantic models |
| ✅ | Format instructions for LLM prompting |

### Embedding Providers (chainforge/rag/embeddings/)

| State | Feature |
|-------|---------|
| ✅ | OpenAIEmbedding — text-embedding-3-small |
| ✅ | HuggingFaceEmbedding — sentence-transformers |
| ✅ | GoogleEmbedding — Gemini embedding API |

### Vector Store Backends (chainforge/rag/vectorstores/)

| State | Feature |
|-------|---------|
| ✅ | ChromaVectorStore — ChromaDB integration |
| ✅ | FAISSVectorStore — FAISS in-memory index |

### Entity Memory (chainforge/memory/entity.py)

| State | Feature |
|-------|---------|
| ✅ | Entity extraction from conversation |
| ✅ | Entity tracking with mention counting |
| ✅ | Context formatting for LLM |

### Toolkits (chainforge/tools/toolkits.py)

| State | Feature |
|-------|---------|
| ✅ | ToolKit base class |
| ✅ | Calculator toolkit (add, multiply, sqrt, power) |
| ✅ | File toolkit (read, write, list) |
| ✅ | Web toolkit (fetch URL) |

### Document Loaders (chainforge/rag/loaders/)

| State | Feature |
|-------|---------|
| ✅ | DirectoryLoader — batch load from directory |
| ✅ | HTMLLoader — HTML tag stripping |

### Prompt Hub (chainforge/prompts/hub.py)

| State | Feature |
|-------|---------|
| ✅ | Template registry (register, get, list, remove) |
| ✅ | Save/load templates from directory |
| ✅ | Variable introspection |

---

## Phase 5: Ecosystem (💡 Future)

### Prompt Templates

| State | Feature |
|-------|---------|
| 🛠 | PromptTemplate — variable injection, from_file, composition |
| 🛠 | ChatPromptTemplate — system/user/assistant message templates |
| 🛠 | FewShotPromptTemplate — example-based prompting |
| 📋 | Template registry and versioning |

### RAG Pipeline

| State | Feature |
|-------|---------|
| 🛠 | Document loaders (Text, CSV, JSON, PDF, HTML) |
| 🛠 | Text splitters (recursive character, token-based, semantic) |
| 🛠 | Embedding providers (OpenAI, local) |
| 🛠 | Vector store abstraction (Chroma, FAISS, in-memory) |
| 🛠 | Retrievers (vector similarity, multi-query, ensemble) |
| 🛠 | RetrievalQA chain |

### LLM Cache

| State | Feature |
|-------|---------|
| 🛠 | Cache interface (get, set, clear, TTL) |
| 🛠 | InMemoryCache implementation |
| 🛠 | Middleware integration |
| 📋 | Redis / persistent cache backends |

---

## Phase 5: Ecosystem (💡 Future)

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
