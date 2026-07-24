
# ChainForge Roadmap

> 路线图：当前状态、短期计划、长期愿景


## Phase 15: Agent Quality & Production Readiness (🛠 In Progress)

### P1: Agent Behavioral Testing Framework

| State | Feature |
|-------|---------|
| 🛠 | **BehaviorTest** — define expected agent behavior as assertions |
| 🛠 | **BehaviorTestRunner** — run tests with MockLLM deterministic replay |
| 📋 | **CI integration** — pytest plugin for agent tests |
| 📋 | **Regression detection** — compare behavior across agent versions |

### P2: Performance Budget Contracts

| State | Feature |
|-------|---------|
| 🛠 | **PerformanceContract** — declare max cost, calls, latency, tools |
| 🛠 | **Budget enforcement** — real-time monitoring of execution against budget |
| 📋 | **Budget learning** — SelfEvolvingAgent learns optimal budgets |

### P1: Agent-as-Microservice

| State | Feature |
|-------|---------|
| 🛠 | **@service decorator** — one-line agent deployment |
| 🛠 | **Auto OpenAPI** — generate OpenAPI spec from agent config |
| 📋 | **MCP auto-registration** — announce service via MCP |

### Priority for Phase 15

1. **Behavioral Testing Framework** — 5-7天, 利用现有 MockLLM + TimeTravelDebugger
2. **Agent-as-Microservice** — 3-5天, 基于现有 server.py
3. **Performance Budget Contracts** — 3-5天, 基于现有 Middleware



## Phase 16: Agent Live Debug Protocol — ALDP (🛠 Implementing)

### ALDP: Agent Debug Protocol

| State | Feature |
|-------|---------|
| 🛠 | **Protocol types** — event/command message schemas (JSON over WebSocket) |
| 🛠 | **WebSocket server** — standalone server with zero extra dependencies |
| 🛠 | **Agent wrapper** — wrap Agent to emit ALDP events |
| 📋 | **Step/pause/resume** — bidirectional control of agent execution |
| 📋 | **Breakpoints** — pause on tool_call, state transition, LLM response |



## Phase 17: Agent Visual Debugger UI (📋 Planned)

> Build a web-based visual debugger for TimeTravelDebugger — the LangGraph Studio equivalent.

### P0: Core Debugger UI

| State | Feature |
|-------|---------|
| 📋 | **Execution timeline** — visual waterfall of agent events (LLM calls, tool calls, state transitions) |
| 📋 | **State inspector** — browse message history, tool results, context at any checkpoint |
| 📋 | **Branch explorer** — fork execution at any checkpoint, compare branches side-by-side |
| 📋 | **Search & filter** — filter events by type, search across messages and tool results |

### P1: Interactive Controls

| State | Feature |
|-------|---------|
| 📋 | **Step-through** — execute one event at a time (step over, step into tool) |
| 📋 | **Breakpoints** — pause on tool_call, error, state transition |
| 📋 | **Replay from checkpoint** — rewind to any point and replay with modifications |
| 📋 | **Live attach** — connect to a running agent and observe in real-time |

### P2: Advanced

| State | Feature |
|-------|---------|
| 📋 | **Provenance graph view** — causal graph of decisions (which input caused which output) |
| 📋 | **Diff view** — compare two execution branches for differences |
| 📋 | **Export/import** — save debug sessions, share with team |

### Architecture

```
React UI (TimeTravelDebugger UI)
    │ WebSocket (ALDP protocol)
    ▼
FastAPI Server (embedded in chainforge serve)
    │ ALDP events
    ▼
ChainForge Agent (wrapped with TimeTravelDebugger)
```

### Priority & Effort

1. **Execution timeline + state inspector** — 5-7d (core value)
2. **Branch explorer + step-through** — 3-5d
3. **Breakpoints + live attach** — 3-5d
4. **Provenance graph + diff view** — 5-7d



## Phase 18: Natural Language → Agent Compiler (📋 Planned)

> Describe agent workflows in natural language; ChainForge compiles them into CyclicGraphs.

### Core Pipeline

| State | Feature |
|-------|---------|
| 📋 | **NL parser** — LLM-based parsing of natural language workflow descriptions |
| 📋 | **Graph IR generator** — convert parsed description into intermediate graph representation |
| 📋 | **CyclicGraph codegen** — emit Python code or YAML for CyclicGraph |
| 📋 | **Validation & feedback** — validate generated graph, report errors and suggestions |

### User Experience

| State | Feature |
|-------|---------|
| 📋 | **CLI mode** — `chainforge compile "search then summarize"` |
| 📋 | **Interactive mode** — chainforge compile --interactive for step-by-step refinement |
| 📋 | **Template library** — common patterns as reusable templates |

### Example

```
$ chainforge compile "search the web, if results found summarize them, 
  otherwise generate a response from knowledge"

→ Generates:
  entry → web_search → [has_results? → yes→ llm_summarize → exit]
                       [has_results? → no → llm_generate → exit]
```

### Effort

1. **NL parser + IR** — 7-10d
2. **CyclicGraph codegen + templates** — 5-7d
3. **Interactive mode + validation** — 3-5d



## Phase 19: Execution Provenance Graph — Upgrade (📋 Planned)

> Upgrade existing TimeTravelDebugger with full causal tracing and provenance graph visualization.

### P1: Causal Tracing Engine

| State | Feature |
|-------|---------|
| 📋 | **Input→Output tracking** — trace every tool result back to its originating LLM call |
| 📋 | **Causal chain query** — `trace_decision(output_id)` returns full causal chain |
| 📋 | **Provenance graph storage** — persist provenance data alongside checkpoints |

### P2: Provenance API

| State | Feature |
|-------|---------|
| 📋 | **REST API** — query provenance data via HTTP (integrated with ALDP) |
| 📋 | **GraphQL-like queries** — "which inputs influenced this output?" |
| 📋 | **Cross-agent provenance** — trace decisions across multi-agent orchestrations |

### P3: Visualization

| State | Feature |
|-------|---------|
| 📋 | **Causal DAG rendering** — visual graph of causal relationships |
| 📋 | **Highlight path** — highlight the critical path for a given output |
| 📋 | **Anomaly detection** — flag decisions with unusual causal depth or breadth |

### Effort

1. **Causal tracing engine** — 5-7d (builds on existing TimeTravelDebugger)
2. **Provenance API + storage** — 3-5d
3. **Visualization** — 5-7d (reuses Debugger UI components)



## Phase 20: Agentic IDE (📋 Future)

> Interactive web-based development environment for building, testing, and deploying agents.

### P0: Agent Playground

| State | Feature |
|-------|---------|
| 📋 | **Chat interface** — talk to your agent in real-time from the browser |
| 📋 | **Live modification** — change system prompt, tools, model while agent is running |
| 📋 | **Tool call inspector** — inspect and modify tool arguments before execution |
| 📋 | **Session persistence** — save and restore agent sessions |

### P1: Development Tools

| State | Feature |
|-------|---------|
| 📋 | **Prompt editor** — syntax-highlighted editor with version history |
| 📋 | **Tool manager** — browse, enable/disable, configure tools |
| 📋 | **Model switcher** — swap models in real-time, compare outputs |
| 📋 | **Memory viewer** — inspect buffer, vector, entity memory contents |

### P2: Deployment

| State | Feature |
|-------|---------|
| 📋 | **One-click deploy** — deploy agent as microservice from the IDE |
| 📋 | **Usage dashboard** — real-time metrics, cost tracking, error rates |
| 📋 | **Version management** — publish, rollback, A/B test agent versions |

### Architecture

```
┌─────────────────────────────────────────────┐
│              Agentic IDE (React)             │
│  Chat  │  Prompt Editor  │  Tools  │  Deploy │
└────┬────────────────────────────────────────┘
     │ REST + WebSocket (ALDP)
     ▼
┌─────────────────────────────────────────────┐
│           ChainForge Server (FastAPI)         │
│  Agent Runtime  │  Config Store  │  Deployer │
└─────────────────────────────────────────────┘
```

### Effort

1. **Agent Playground (chat + live modify)** — 7-10d
2. **Development tools (prompt/tool/memory editors)** — 7-10d
3. **Deployment dashboard** — 5-7d



## Phase 21: Self-Healing Agents (📋 Future)

> Agents that detect failures, diagnose root causes, and automatically recover.

### P0: Failure Detection

| State | Feature |
|-------|---------|
| 📋 | **Error pattern recognition** — classify failures (tool error, LLM refusal, timeout, hallucination) |
| 📋 | **Success rate tracking** — per-tool, per-model, per-prompt success metrics |
| 📋 | **Anomaly detection** — detect when agent behavior deviates from expected patterns |

### P1: Auto-Diagnosis

| State | Feature |
|-------|---------|
| 📋 | **Root cause analysis** — trace failure back to its cause (bad prompt, wrong tool, insufficient context) |
| 📋 | **Healing strategy selection** — choose fix strategy: retry, rephrase, switch tool, escalate |
| 📋 | **Diagnosis report** — structured report of what went wrong and why |

### P2: Self-Recovery

| State | Feature |
|-------|---------|
| 📋 | **Automatic retry with modification** — retry with adjusted parameters |
| 📋 | **Prompt auto-patch** — modify system prompt to prevent recurrence |
| 📋 | **Tool fallback chain** — define fallback tools for common failure modes |
| 📋 | **Sub-agent creation** — spawn specialized sub-agent to handle recurring failure patterns |

### Effort

1. **Failure detection + tracking** — 5-7d
2. **Root cause analysis** — 5-7d (uses Execution Provenance Graph)
3. **Self-recovery strategies** — 7-10d



## Phase 22: Agent Memory Consolidation (📋 Future)

> Simulate human memory consolidation — periodic review, pattern extraction, and pruning.

### P0: Memory Review Engine

| State | Feature |
|-------|---------|
| 📋 | **Periodic consolidation** — configurable consolidation schedule (every N turns, every hour, etc.) |
| 📋 | **Pattern extraction** — LLM analyzes memories to extract recurring themes and facts |
| 📋 | **Confidence scoring** — assign confidence to memories based on frequency and consistency |

### P1: Memory Pruning & Archival

| State | Feature |
|-------|---------|
| 📋 | **Low-confidence pruning** — remove memories below confidence threshold |
| 📋 | **Semantic compression** — merge related memories into condensed summaries |
| 📋 | **Hierarchical archiving** — working → episodic → semantic memory migration |

### P2: Integration

| State | Feature |
|-------|---------|
| 📋 | **AutoMemoryManager integration** — plug into existing AutoMemoryManager |
| 📋 | **Memory quality metrics** — track precision/recall of consolidated memories |
| 📋 | **User-guided consolidation** — allow users to review and correct consolidation |

### Effort

1. **Memory review + confidence scoring** — 5-7d
2. **Pruning + compression** — 5-7d
3. **Integration + metrics** — 3-5d



## Phase 23: Federated Agent Execution (📋 Future)

> Agents delegate sub-tasks to agents on other machines, clouds, or frameworks.

### P0: Agent Discovery

| State | Feature |
|-------|---------|
| 📋 | **Agent registry** — register and discover remote agents via A2A protocol |
| 📋 | **Capability advertisement** — agents publish their capabilities as structured specs |
| 📋 | **Health checking** — monitor remote agent availability and latency |

### P1: Remote Execution

| State | Feature |
|-------|---------|
| 📋 | **Remote tool call** — call a remote agent's tool as if it were local |
| 📋 | **Streaming across boundaries** — stream events from remote agent execution |
| 📋 | **Cross-framework bridge** — call LangChain/CrewAI/AutoGen agents via A2A |

### P2: Orchestration

| State | Feature |
|-------|---------|
| 📋 | **Global planner** — plan task decomposition across distributed agents |
| 📋 | **Result aggregation** — collect and merge results from multiple remote agents |
| 📋 | **Fault tolerance** — retry with different remote agent on failure |

### Effort

1. **Agent registry + discovery** — 5-7d (builds on A2A protocol)
2. **Remote execution** — 5-7d
3. **Orchestration + fault tolerance** — 5-7d



## Phase 24: Auditable Execution Chain (📋 Future)

> Cryptographically signed agent execution logs for compliance, auditing, and debugging.

### P0: Execution Logging

| State | Feature |
|-------|---------|
| 📋 | **Immutable log** — append-only log of all agent actions (LLM calls, tool calls, decisions) |
| 📋 | **Merkle tree chaining** — each entry cryptographically hashed to the previous |
| 📋 | **Signature verification** — verify log integrity with public key |

### P1: Compliance & Audit

| State | Feature |
|-------|---------|
| 📋 | **Audit query** — search execution logs by criteria (user, tool, time range, decision) |
| 📋 | **Compliance report generation** — produce structured compliance reports |
| 📋 | **Redaction** — selectively redact sensitive data while preserving chain integrity |
| 📋 | **Export** — export signed logs in standard formats (JSON, CSV, XLSX) |

### P2: Integration

| State | Feature |
|-------|---------|
| 📋 | **Middleware integration** — plug into existing middleware chain |
| 📋 | **Callback integration** — log via existing Callback system |
| 📋 | **SIEM export** — export to standard SIEM formats (CEF, LEEF) |

### Effort

1. **Immutable log + Merkle chaining** — 5-7d
2. **Audit query + compliance reports** — 5-7d
3. **Integration + SIEM export** — 3-5d



## Phase 25: Adversarial Testing Engine (📋 Future)

> Automated adversarial testing for agent security and robustness.

### P0: Attack Generation

| State | Feature |
|-------|---------|
| 📋 | **Prompt injection generation** — auto-generate prompt injection attacks (50+ patterns) |
| 📋 | **Jailbreak generation** — generate jailbreak attempts targeting the system prompt |
| 📋 | **Edge case fuzzing** — generate unexpected inputs (empty, very long, malformed) |

### P1: Automated Testing

| State | Feature |
|-------|---------|
| 📋 | **Test runner** — run generated attacks against agent, collect results |
| 📋 | **Defense evaluation** — test guardrails (PromptInjectionGuardrail) against attacks |
| 📋 | **Regression testing** — re-run attacks after agent changes to detect regressions |

### P2: Reporting

| State | Feature |
|-------|---------|
| 📋 | **Security score** — aggregate security score based on attack success rate |
| 📋 | **Vulnerability report** — structured report of discovered vulnerabilities |
| 📋 | **Improvement suggestions** — auto-suggest guardrail improvements based on findings |

### Effort

1. **Attack generation pipeline** — 5-7d (uses existing Eval framework)
2. **Automated testing + regression** — 5-7d
3. **Reporting + score** — 3-5d



## Phase 26: Adaptive Multi-Model Router — SmartRouter 2.0 (📋 Future)

> Route sub-tasks to different models in real-time based on capability, cost, and latency.

### P0: Capability-Aware Routing

| State | Feature |
|-------|---------|
| 📋 | **Capability registry** — each model declares capabilities (reasoning, code, vision, function-calling) |
| 📋 | **Task capability inference** — infer required capabilities from task description |
| 📋 | **Real-time model selection** — select best model for each sub-task |

### P1: Cost-Latency Optimization

| State | Feature |
|-------|---------|
| 📋 | **Cost tracking** — per-model cost accumulation |
| 📋 | **Latency tracking** — per-model latency distribution |
| 📋 | **Cost-latency tradeoff** — configurable objective (min cost, min latency, or balanced) |

### P2: Dynamic Switching

| State | Feature |
|-------|---------|
| 📋 | **Mid-execution switch** — switch models mid-task if current model is underperforming |
| 📋 | **Fallback chains** — try model A, fall back to B if A fails, fall back to C if B fails |
| 📋 | **Sticky routing** — keep same model for related sub-tasks when beneficial |

### Effort

1. **Capability registry + inference** — 5-7d
2. **Cost-latency optimization** — 3-5d
3. **Dynamic switching + fallback** — 5-7d



## Phase 27: Agent Behavior Contract Runtime (📋 Future)

> Formalize ASL (Agent Specification Language) into a runtime-executable contract.

### P0: Contract Execution

| State | Feature |
|-------|---------|
| 📋 | **Contract parser** — parse ASL YAML into executable contract objects |
| 📋 | **Runtime enforcement** — monitor agent execution against contract (budget, behavior, tools) |
| 📋 | **Violation reporting** — structured violation reports with causal context |

### P1: Contract Types

| State | Feature |
|-------|---------|
| 📋 | **Behavior contracts** — "agent should never reveal system prompt" |
| 📋 | **Performance contracts** — "response under 5s, cost under $0.01" |
| 📋 | **Security contracts** — "never call delete_file tool" |
| 📋 | **Quality contracts** — "always cite sources, never hallucinate" |

### P2: Contract Lifecycle

| State | Feature |
|-------|---------|
| 📋 | **Contract testing** — validate contracts before deployment |
| 📋 | **Contract versioning** — evolve contracts across agent versions |
| 📋 | **Auto-remediation** — define actions on contract violation (warn, block, escalate) |

### Effort

1. **Contract parser + enforcement** — 5-7d
2. **Contract types + validators** — 5-7d
3. **Contract lifecycle + remediation** — 3-5d



## Phase 28: Activity Log Dashboard (📋 Future)

> Real-time web dashboard for structured activity logs.

### P0: Log Viewer

| State | Feature |
|-------|---------|
| 📋 | **Real-time feed** — live streaming of activity events |
| 📋 | **Filter & search** — filter by category, level, tool, session |
| 📋 | **Timeline view** — chronological view with severity color coding |

### P1: Analytics

| State | Feature |
|-------|---------|
| 📋 | **Aggregated metrics** — request rate, error rate, latency distribution |
| 📋 | **Tool usage stats** — most/least used tools, failure rates per tool |
| 📋 | **Cost analytics** — per-model, per-session, per-user cost breakdown |

### P2: Alerting

| State | Feature |
|-------|---------|
| 📋 | **Threshold alerts** — alert on error rate > X%, latency > Yms |
| 📋 | **Anomaly detection** — detect unusual activity patterns |
| 📋 | **Webhook integration** — forward alerts to PagerDuty, Slack, etc. |

### Effort

1. **Log viewer + filters** — 5-7d (builds on ActivityLogger + existing server.py)
2. **Analytics dashboard** — 5-7d
3. **Alerting + webhooks** — 3-5d



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

### Guardrails (Input/Output Safety)

| State | Feature |
|-------|---------|
| ✅ | InjectionDetector — prompt injection & jailbreak detection |
| ✅ | TopicFilter — allow/block topic restrictions |
| ✅ | PIILeakGuard — prevent sensitive data leakage in outputs |
| ✅ | ContentSafetyGuard — detect harmful content |
| ✅ | ToolPermissionPolicy — allow/block/dangerous tool lists |
| ✅ | QualityGuard — basic output quality checks |
| ✅ | GuardrailMiddleware — integrate into Agent pipeline |

### Code Sandbox + Multi-modal

| State | Feature |
|-------|---------|
| 🛠 | Subprocess sandbox (safe Python code execution) |
| 📋 | Docker sandbox (full isolation) |
| 📋 | Built-in `@tool` for code execution |
| ✅ | Multi-modal Message parts (image, file, audio) |
| 📋 | File loader utilities |
| 📋 | Image input in providers |

### Memory 2.0 (Vector Memory)

| State | Feature |
|-------|---------|
| 🛠 | Embedding function protocol |
| 🛠 | VectorMemory with semantic retrieval |
| 📋 | Hierarchical memory (working -> episodic -> semantic) |
| 📋 | Cross-session persistent memory |
| 📋 | Memory manager coordinating multiple backends |

### Agent Config Declaration

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

| | Description |
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

### Conversation Serialization (chainforge/core/conversation.py)

| State | Feature |
|-------|---------|
| ✅ | Conversation class — manage message history |
| ✅ | JSON save/load with metadata |
| ✅ | Integration with agent.run() |
| ✅ | Auto-capture assistant responses |

### Bug Fixes

| State | Fix |
|-------|-----|
| ✅ | SummaryMemory auto-compress without LLM |
| 📋 | Bedrock streaming tool call accumulation (PLAN.md #2) |

### Agent Callback System (chainforge/callbacks/)

| State | Feature |
|-------|---------|
| ✅ | Callback protocol — one-way observability hooks |
| ✅ | LoggingCallback — structured event logging |
| ✅ | MetricsCallback — timing, counters, tool tracking |
| ✅ | Agent integration — 7 hook points in run loop |
| ✅ | Error resilience — exceptions never break agent |

### Reasoning Strategies (chainforge/reasoning/)

| State | Feature |
|-------|---------|
| ✅ | ReasoningStrategy protocol — composable hooks into Agent loop |
| ✅ | ChainOfThought — step-by-step thinking injection |
| ✅ | ReasoningSteps — explicit sub-step planning |
| ✅ | SelfReflection — self-critique and improvement |
| ✅ | Verification — double-check before final answer |
| ✅ | Agent integration — before_llm/after_llm/on_tool_result/should_stop |

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



## Phase 7: Remaining Gaps (📋 Planned, from Gap Analysis 2026-07)

### Agent-Run Loop Migration

| State | Feature |
|-------|---------|
| ✅ | CyclicGraph execution engine |
| ✅ | Migrate Agent._run_loop to CyclicGraph execution (replace hand-written state machine) |
| 💡 | Full visual agent flow graph in dashboard |

### LLM Response Extensions

| State | Feature |
|-------|---------|
| ✅ | LLMResponse.reasoning_content — thinking model support (DeepSeek-R1, o-series) |
| ✅ | LLMResponse.cost — aggregated cost tracking from token usage |
| ✅ | Provider capability declaration (supports_vision, supports_tools, supports_streaming, etc.) |

### Tool System Evolution

| State | Feature |
|-------|---------|
| ✅ | Structured tool artifacts (non-string returns via response_schema) |
| ✅ | BaseTool class with _run / _arun lifecycle methods |
| ✅ | OpenAPIToolkit — spec-to-tool auto-generation |
| 💡 | Streaming tool execution support |

### Evaluation Depth

| State | Feature |
|-------|---------|
| ✅ | LLMJudgeEval — LLM-as-judge scoring |
| ✅ | PairwiseEval — A/B comparison |
| ✅ | Adversarial testing (prompt injection, jailbreak scenarios) |
| ✅ | Regression test suite with auto-detection |

### Agentic RAG

| State | Feature |
|-------|---------|
| ✅ | Self-RAG — agent decides when to retrieve |
| ✅ | Corrective RAG — agent evaluates and fixes retrieval quality |
| 💡 | Adaptive RAG — agent chooses retrieval strategy per query |

### Computer Use / Advanced Tools

| State | Feature |
|-------|---------|
| ✅ | PlaywrightTool — browser automation for agents |
| ✅ | Deep MCP integration — auto-discover and connect MCP servers |
| ✅ | Knowledge Graph Memory (Neo4j-style entity-relation store) |
| ✅ | Cron/scheduled agent execution |

### Priority for Phase 7

1. **Agent._run_loop -> CyclicGraph** — 架构级整合，释放 CyclicGraph 全部价值
2. **LLMResponse.reasoning_content + cost + Provider capability** — 跟上模型演进
3. **Structured tool artifacts + BaseTool + OpenAPIToolkit** — Tool 组合性核心缺口
4. **Adversarial testing + Agentic RAG** — 安全与检索增强
5. **Computer Use + Deep MCP + Knowledge Graph + Cron** — 前沿能力
## How to prioritize

1. **Sandbox + Multi-modal** — 2025 Agent 的基本能力，缺了就感觉不完整
2. **Memory 2.0** — 语义记忆是复杂 Agent 的基础设施
3. **Agent Config** — 让 Agent 能被声明和管理，走向更广泛用户

## Phase 6: Architecture Deepening (📋 Planned, from Gap Analysis 2026-07)

### Graph Execution Engine

| State | Feature |
|-------|---------|
| ✅ | DAG — acyclic graph execution with topological sort |
| ✅ | CyclicGraph — support cycles for agent loops, reflection, retry |
| ✅ | Conditional edges — state-driven routing (routing_fn pattern) |
| ✅ | Node types — agent / tool / router / conditional / entry / exit |
| 💡 | Migrate Agent._run_loop to CyclicGraph execution |

### State Persistence / Checkpointing

| State | Feature |
|-------|---------|
| ✅ | Checkpointer protocol (save, load, list_threads, list_checkpoints) |
| ✅ | InMemoryCheckpointer implementation |
| ✅ | SQLiteCheckpointer implementation |
| ✅ | thread_id based session isolation |
| ✅ | Agent.run() thread_id parameter |

### Multi-Agent Topology Expansion

| State | Feature |
|-------|---------|
| ✅ | Swarm (parallel/sequential/conference) |
| ✅ | Supervisor (flat delegation) |
| ✅ | AgentChain (linear sequence) |
| ✅ | Network topology — agent-to-agent direct messaging |
| ✅ | Hierarchical teams — recursive supervisor nesting |
| ✅ | Debate — multi-agent argumentation for consensus |

### Memory Depth

| State | Feature |
|-------|---------|
| ✅ | Auto-summarize — MemoryManager.summarize() with LLM |
| ✅ | SQLite-backed VectorMemory — cross-session persistence |
| ✅ | EntityMemory graph — neighbor/relation tracking |
| ✅ | trim_messages / summarize_messages utility functions |
| ✅ | Knowledge Graph Memory (Neo4j-style) |

### Tool System Evolution

| State | Feature |
|-------|---------|
| ✅ | Structured tool artifacts (non-string returns) |
| ✅ | BaseTool class with _run / _arun lifecycle |
| ✅ | OpenAPIToolkit — spec-to-tool auto-generation |
| 💡 | Streaming tool execution support |

### Provider & Multi-modal

| State | Feature |
|-------|---------|
| ✅ | 5 cloud providers (OpenAI, Anthropic, Google, Azure, Bedrock) |
| ✅ | OllamaProvider — local inference |
| ✅ | Multi-modal Message parts (image, file, audio) |
| ✅ | LLMResponse.reasoning_content — thinking model support |
| ✅ | LLMResponse.cost — aggregated cost tracking |
| ✅ | Provider capability declaration (supports_vision, etc.) |
| 💡 | vLLM / LlamaCpp providers |

### Evaluation Depth

| State | Feature |
|-------|---------|
| ✅ | EvalCase/EvalSuite/EvalRunner/EvalReport framework |
| ✅ | LLMJudgeEval — LLM-as-judge scoring |
| ✅ | PairwiseEval — A/B comparison with Elo rating |
| ✅ | Adversarial testing (prompt injection, jailbreak scenarios) |

### Production Deployment

| State | Feature |
|-------|---------|
| ✅ | FastAPI REST + SSE server |
| ✅ | Thread/session management API |
| ✅ | Webhook callback on agent completion |
| ✅ | API key authentication |
| ✅ | Usage quota / rate limiting per user |
| ✅ | Cron/scheduled agent execution |

### Forward-looking Features

| State | Feature |
|-------|---------|
| ✅ | MCP client (basic) |
| ✅ | A2A protocol (Agent-to-Agent) |
| 💡 | Computer Use / Playwright Tool |
| 💡 | Agentic RAG (Self-RAG / Corrective RAG / Adaptive RAG) |
| 💡 | Deep MCP integration (dynamic tool discovery) |

### Priority for Phase 6

1. **CyclicGraph + Checkpointing** — 架构级缺失，影响所有 agent 流程
2. **Network topology** — 多 agent 组合多样性
3. **Memory 持久化 (SQLite VectorStore)** — 跨会话记忆保真度
4. **OllamaProvider + Multi-modal Message** — 降低使用门槛
5. **LLMJudgeEval** — 评估信度
6. **Production deployment (auth, webhook, quota)** — 生产部署必备

## Phase 8: Production Hardening & Benchmarks (📋 Planned, from Gap Analysis 2026-07)

### Code Sandbox Evolution

| State | Feature |
|-------|---------|
| ✅ | SubprocessSandbox — process-level isolation |
| ✅ | DockerSandbox — container-level isolation |
| 💡 | E2B sandbox integration |

### State Streaming + Debugger

| State | Feature |
|-------|---------|
| ✅ | Full state snapshot streaming (complete state dict per step) |
| ✅ | Step debugger — pause, inspect, resume agent execution |
| 💡 | LangGraph Studio-style visual debug UI |

### Benchmark Integration

| State | Feature |
|-------|---------|
| ✅ | BFCL (Berkeley Function Calling Leaderboard) test cases |
| ✅ | GAIA / ToolBench benchmark suites |
| ✅ | Automated benchmark runner |

### Vector Store Expansion

| State | Feature |
|-------|---------|
| ✅ | ChromaVectorStore, FAISSVectorStore, InMemoryVectorStore, SQLiteVectorMemory |
| 💡 | Pinecone / Weaviate / Milvus / Qdrant backends |

### Document Loader Expansion

| State | Feature |
|-------|---------|
| ✅ | Text, CSV, JSON, HTML, Directory loaders |
| 💡 | Notion / Confluence / GitHub / Slack / YouTube loaders |

### GraphRAG Pipeline

| State | Feature |
|-------|---------|
| ✅ | KnowledgeGraphMemory — entity-relation graph store |
| 💡 | Community detection + summarization (GraphRAG pattern) |

### Constrained Decoding

| State | Feature |
|-------|---------|
| 💡 | Outlines / lm-format-enforcer integration for token-level structured output |

### MemGPT-style Auto Memory

| State | Feature |
|-------|---------|
| 💡 | Automatic memory archival, retrieval-triggered recall, conflict resolution |

### Priority for Phase 8

1. **Docker Sandbox** — Agent 执行代码必须容器隔离
2. **State streaming + Debugger** — 对标 LangGraph Studio 的调试能力
3. **BFCL benchmark** — 可信的工具调用评估
4. **Vector store breadth** — Pinecone/Milvus/Qdrant 适配
5. **Document loader breadth** — 扩充 RAG 数据源


## Phase 9: Frontier Agent Capabilities & Ecosystem Breadth (📋 Planned)

### Frontier: Constrained Decoding

| State | Feature |
|-------|---------|
| 📋 | Outlines / lm-format-enforcer integration — token-level constrained structured output |
| 📋 | JSON mode fallback — automatic retry with grammar constraints |

### Frontier: MemGPT-style Auto Memory

| State | Feature |
|-------|---------|
| 📋 | Automatic memory archival — move old context to long-term storage |
| 📋 | Retrieval-triggered recall — auto-query memory when relevant |
| 📋 | Conflict resolution — handle contradictory stored facts |
| 📋 | Forgetting curve — deprioritize old/unused memories |

### Frontier: Runtime Tool Discovery

| State | Feature |
|-------|---------|
| 📋 | Dynamic tool registry — agents discover tools at runtime |
| 📋 | Tool capability query — agents inspect tool capabilities before calling |
| 📋 | Auto-connect MCP servers — discover + register tools without restart |

### Ecosystem: Vector Store Breadth

| State | Feature |
|-------|---------|
| ✅ | Chroma, FAISS, SQLite, InMemory vector stores |
| 📋 | PineconeVectorStore — Pinecone cloud vector DB |
| 📋 | QdrantVectorStore — Qdrant vector search engine |

### Ecosystem: Document Loader Breadth

| State | Feature |
|-------|---------|
| ✅ | Text, CSV, JSON, HTML, Directory loaders |
| 📋 | PDFLoader — PDF parsing with text extraction |
| 📋 | NotionLoader — Notion pages and databases |
| 📋 | GitHubLoader — GitHub repos, issues, PRs |

### Ecosystem: Visual Debugger

| State | Feature |
|-------|---------|
| ✅ | StepDebugger — CLI-based pause/inspect/step |
| 💡 | Web debugger — LangGraph Studio-style visual step-through in Dashboard |

### Priority for Phase 9

1. **Constrained Decoding** — 结构化输出可靠性从 ~90% 提升至 99%+
2. **MemGPT-style Auto Memory** — 长对话记忆保真度的根本解决方案
3. **Runtime Tool Discovery** — 动态工具发现的架构级能力
4. **Vector Store Breadth** — Pinecone + Qdrant 覆盖主流生产场景
5. **Document Loader Breadth** — PDF + Notion + GitHub 扩充 RAG 数据源
6. **Visual Debugger** — Web UI 调试界面




## Phase 10: Monitoring, Routing & GraphRAG (📋 Planned)

### Monitoring / Trace Viewer

| State | Feature |
|-------|---------|
| ✅ | Tracing infrastructure (ConsoleTracer, OpenTelemetry, Langfuse) |
| 📋 | Trace storage — persist traces to SQLite for querying |
| 📋 | Trace viewer API — query traces by agent_id, session, time range |
| 📋 | Dashboard trace page — `/dashboard/traces` with timeline visualization |
| 📋 | Cost aggregation — total cost per agent/session/time period |
| 📋 | Feedback collection — rate agent responses from dashboard |

### Model Router

| State | Feature |
|-------|---------|
| 📋 | SmartRouter — classify task complexity and route to optimal model |
| 📋 | Cost-optimized routing — use cheap model for simple tasks |
| 📋 | Fallback routing — retry with better model on failure |
| 📋 | Provider capability-aware routing — match task to model strengths |

### GraphRAG Pipeline

| State | Feature |
|-------|---------|
| ✅ | KnowledgeGraphMemory — entity-relation graph store |
| 📋 | Community detection — Leiden/ Louvain clustering |
| 📋 | Community summarization — LLM-generated summaries per community |
| 📋 | GraphRAG query — retrieve by entity → community → summary |

### Priority for Phase 10

1. **Trace Viewer (Monitoring UI)** — 生产运维的最短板
2. **Model Router** — 直接降成本 50-80%
3. **GraphRAG Pipeline** — 知识图谱检索的下一阶段


## Phase 11: Agent Frontier — Revolutionary Features (🛠 In Progress)

### P0: CyclicGraph with Conditional Routing

| State | Feature |
|-------|---------|
| ✅ | DAG execution engine (topological sort, branch/join) |
| ✅ | CyclicGraph with cycle support, conditional edges |
| 🛠 | **Checkpoint integration** — persist execution state across pause/resume |
| 🛠 | **Multi-round execution** — max_iterations with configurable terminal detection |
| 📋 | **Thread session management** — thread_id based conversation isolation |

### P0: Checkpoint System

| State | Feature |
|-------|---------|
| ✅ | Checkpointer protocol (save/load/list/delete) |
| ✅ | InMemoryCheckpointer — in-process checkpoint storage |
| ✅ | SQLiteCheckpointer — persistent checkpoint storage |
| 🛠 | **Agent.run() thread_id** — bind checkpointer to agent execution |
| 🛠 | **Auto-checkpoint** — automatic checkpoint on state transitions |

### P1: Time-Travel Debugger

| State | Feature |
|-------|---------|
| 🛠 | StepDebugger with pause/resume/step/abort |
| 🛠 | **Checkpoint replay** — rewind and replay from any checkpoint |
| 🛠 | **Branch execution** — fork execution from a specific checkpoint |
| 📋 | **State diff** — compare state between two checkpoints |
| 📋 | **Web debugger** — visual step-through in Dashboard |

### P2: Cross-Model Consensus Protocol

| State | Feature |
|-------|---------|
| 🛠 | ConsensusAgent — run same query across multiple models |
| 🛠 | **Vote strategies** — majority, confidence-weighted, detailed |
| 📋 | **Fallback chain** — cascade through models until success |
| 📋 | **Cost optimization** — cheapest model that meets quality threshold |

### P2: Self-Evolving Agent

| State | Feature |
|-------|---------|
| 🛠 | ExecutionMetricsRecorder — record tool usage, errors, patterns |
| 🛠 | **Auto-optimize** — analyze execution and improve system prompt |
| 📋 | **Tool selection** — learn which tools work best for which tasks |
| 📋 | **Strategy adaptation** — evolve reasoning strategy over time |

### P3: NL-as-Code Compiler

| State | Feature |
|-------|---------|
| 📋 | **Workflow parser** — natural language to DAG |
| 📋 | **Type checking** — validate data flow between steps |
| 📋 | **Compile to CyclicGraph** — executable output |

### P3: Agent Swarm Intelligence

| State | Feature |
|-------|---------|
| 📋 | **Blackboard communication** — shared context layer |
| 📋 | **Emergent behavior** — consensus-driven stopping |
| 📋 | **Role specialization** — agents self-assign roles |

### Priority for Phase 11

1. **Time-Travel Debugger** — 极大地提升 Agent 开发效率，是 LangChain 没有的差异化功能
2. **Cross-Model Consensus** — 多模型仲裁直接提升答案质量 20-30%
3. **Self-Evolving Agent** — 自我进化的 Agent 是通往 AGI 的关键路径
4. **Agent.run() thread_id** — 为所有高级功能提供会话基础设施
5. **NL-as-Code Compiler** — 自然语言编程的桥梁
6. **Swarm Intelligence** — 群体智能的涌现行为探索



## Phase 12: Agent Frontier — Second Wave of Revolutionary Features (🛠 In Progress)

### P0: Adaptive Tool Synthesis

| State | Feature |
|-------|---------|
| 🛠 | **Tool synthesis in Sandbox** — agent writes, tests, and registers new tools at runtime |
| 📋 | Tool caching — same-signature tools are reused across sessions |
| 📋 | Synthesis policy — on_demand and proactive (anticipate tool needs) |

### P0: Visual Debugger UI

| State | Feature |
|-------|---------|
| 📋 | **Web-based step-through** — React SPA for TimeTravelDebugger |
| 📋 | State inspection — view messages, context, tool results in tree view |
| 📋 | Replay controls — rewind, step, branch, compare |

### P1: Liquid Time-Series Memory

| State | Feature |
|-------|---------|
| 🛠 | **Decay-based forgetting** — memory weights decay over time (exp(-t/tau)) |
| 🛠 | **Frequency boosting** — frequently accessed memories have enhanced weight |
| 📋 | Auto-consolidation — merge semantically similar low-weight memories |

### P1: Execution Provenance Graph

| State | Feature |
|-------|---------|
| 📋 | **Causal link tracking** — each event records what caused it |
| 📋 | Provenance query — "why did the agent do X?" |

### P2: Prompt Injection Detection

| State | Feature |
|-------|---------|
| 🛠 | **Pattern-based detection** — known injection pattern matching |
| 📋 | LLM-based detection — secondary LLM evaluates prompt safety |
| 📋 | Automatic response modes — block, flag, sanitize |

### Priority for Phase 12

1. **Adaptive Tool Synthesis** — 独家壁垒，框架级能力
2. **Liquid Time-Series Memory** — 解决长上下文天花板
3. **Prompt Injection Detection** — 安全补短板
4. **Visual Debugger UI** — 追上 LangGraph Studio
5. **Execution Provenance Graph** — 调试器升级



## Phase 13: Execution Intelligence & Multimodal (🛠 In Progress)

### P1: Execution Provenance Graph

| State | Feature |
|-------|---------|
| 🛠 | **Causal link tracking** — each StreamEvent records what caused it |
| 🛠 | **Provenance query** — trace_decision() shows full causal chain |
| 📋 | **Provenance visualization** — graph rendering of execution causality |

### P2: Declarative Workflow DSL

| State | Feature |
|-------|---------|
| 🛠 | **YAML workflow parser** — define CyclicGraph as YAML |
| 📋 | **JSON schema validation** — validate workflow at load time |
| 📋 | **Workflow templates** — reusable workflow component library |

### P3: Multi-Modal Pipeline

| State | Feature |
|-------|---------|
| 🛠 | **Image input via file path** — load_image() for vision models |
| 📋 | **Audio input** — speech-to-text preprocessing |
| 📋 | **Unified multimodal router** — auto-detect input type and route |

### Priority for Phase 13

1. **Execution Provenance Graph** — 把 TimeTravelDebugger 升级为因果推理引擎
2. **Declarative Workflow DSL** — 让非程序员也能定义 Agent 工作流
3. **Multi-Modal Pipeline** — 补齐多模态输入能力


## Phase 14: Self-Optimizing Agents (🛠 Just Implemented)

### Dream / Simulation Mode

| State | Feature |
|-------|---------|
| 🛠 | **DreamConfig** — light/medium/deep prediction levels, accuracy tracking |
| 🛠 | **Compare & learn** — prediction vs actual discrepancy analysis |
| 📋 | **Auto-retry** — re-predict when accuracy is low |

### Technology Tree

| State | Feature |
|-------|---------|
| 🛠 | **TechTree** — capability tree with unlock conditions |
| 🛠 | **Usage tracking** — tool use counting for unlock triggers |
| 🛠 | **Listener callbacks** — on_unlock event hooks |
| 📋 | **Visualization** — tree rendering and progress tracking |

### Multi-Generational Evolution

| State | Feature |
|-------|---------|
| 🛠 | **AgentPopulation** — genetic algorithm framework |
| 🛠 | **Tournament selection** — fitness-proportional parent selection |
| 🛠 | **Crossover + mutation** — genome blending and random variation |
| 🛠 | **Elite preservation** — keep top performers across generations |

