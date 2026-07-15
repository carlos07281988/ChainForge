# Phase 11-15 Design Document

> Comprehensive design documentation for all 17 features implemented across Phases 11-15.

---

## Overview

| Phase | Features | Tests |
|-------|----------|-------|
| 11 | TimeTravelDebugger, ConsensusAgent, SelfEvolvingAgent, thread_id | 46 |
| 12 | ToolSynthesizer, LiquidMemory, PromptInjectionGuardrail | 30 |
| 13 | Execution Provenance Graph, Workflow DSL, Multi-Modal Pipeline | 20 |
| 14 | Dream Mode, Technology Tree, Population Evolution | 29 |
| 15 | Behavioral Testing, Performance Budget, Agent-as-Microservice | 22 |
| **Total** | **17 features** | **147 new tests** |

---

## Phase 11: Agent Frontier

### TimeTravelDebugger

**File**: `chainforge/core/time_travel.py`

Records full execution snapshots at each state transition, enabling time-travel debugging.

**Key Classes**:
- `TimeTravelDebugger` — wraps an Agent, records checkpoints during execution
- `ExecutionCheckpoint` — snapshot of execution state at a point in time

**API**:
- `run(prompt, auto_checkpoint=True)` — execute with recording
- `replay(checkpoint_id)` — replay events from a checkpoint
- `branch(checkpoint_id)` — fork execution from a checkpoint
- `diff(checkpoint_id_a, checkpoint_id_b)` — compare two checkpoints
- `provenance_graph()` — build causal execution graph
- `trace_decision(target_content)` — trace why an output occurred
- `explain(target_content)` — human-readable explanation

**Usage**:
```python
debugger = TimeTravelDebugger(agent)
stream = await debugger.run("Analyze this")
trace = debugger.trace_decision("42")
explanation = debugger.explain("42")
```

### ConsensusAgent

**File**: `chainforge/orchestration/consensus.py`

Runs the same prompt across multiple models and resolves differences.

**Strategies**:
- `majority_vote` — most common answer wins
- `confidence_weighted` — weighted by model confidence
- `detailed` — all responses preserved for comparison
- `fallback_chain` — try models sequentially until success

**Key Types**:
- `ConsensusAgent(Agent)` — extends base Agent with multi-model support
- `ConsensusStrategy` — enum of strategies
- `ModelVote` — single model's response
- `ConsensusResult` — computed consensus

### SelfEvolvingAgent

**File**: `chainforge/agents/self_evolving.py`

Records execution metrics and progressively improves system prompts.

**Key Types**:
- `SelfEvolvingAgent(Agent)` — agent with evolution capabilities
- `ExecutionMetrics` — tool calls, errors, response length, success rate

**Flow**:
1. Each run records metrics (tool_calls, tool_errors, response_length, success)
2. After `min_runs_for_evolution` runs, analyzes patterns
3. Generates improvement descriptions
4. Evolves system prompt with insights

---

## Phase 12: Second Wave

### ToolSynthesizer

**File**: `chainforge/tools/synthesis.py`

Agents write, test, and register tools at runtime using LLM + code verification.

**Flow**:
1. LLM generates Python function from natural language description
2. Syntax validation via `ast.parse()`
3. Execution test with sample inputs
4. ToolSpec extraction from function signature
5. FunctionTool registration
6. Cache for reuse

**Key Types**:
- `ToolSynthesizer` — main synthesis engine
- `ToolCache` — deduplication cache keyed by intent hash
- `SynthesizedTool` — metadata about synthesized tool

### LiquidMemory

**File**: `chainforge/memory/liquid.py`

Time-series memory with exponential decay and frequency-enhanced retention.

**Parameters**:
- `decay_rate` — exponential decay rate (default 0.05)
- `frequency_boost` — weight multiplier on access (default 1.5)
- `max_items` — maximum items (default 1000)
- `min_weight` — auto-prune threshold (default 0.05)

**Query Methods**:
- `get_context(top_k)` — highest-weighted items
- `query(text, top_k)` — keyword matching weighted by decay + frequency
- `get_by_tags(tags, top_k)` — tag-based filtering

### PromptInjectionGuardrail

**File**: `chainforge/guardrails/injection.py`

Detects prompt injection with 15+ pattern categories.

**Detection Categories**:
- `instruction_override` — "ignore all instructions"
- `role_play` — "you are now DAN"
- `prompt_leak` — "show your system prompt"
- `delimiter_confusion` — "new prompt:"
- `encoding_abuse` — base64 injection
- `harmful` — weapon creation, hacking, phishing

---

## Phase 13: Execution Intelligence

### Execution Provenance Graph

**File**: `chainforge/core/time_travel.py` (methods added to TimeTravelDebugger)

Causal chain tracking that records why each event occurred.

**Methods**:
- `provenance_graph()` — full causal graph
- `_infer_cause(event, index)` — backward causal inference
- `trace_decision(target, max_depth)` — walk causal chain
- `explain(target)` — human-readable trace

### Declarative Workflow DSL

**File**: `chainforge/core/graph_dsl.py`

Define CyclicGraph workflows as YAML/JSON.

**Functions**:
- `parse_workflow_dict(data)` — dict to CyclicGraph
- `parse_workflow_json(json_str)` — JSON to CyclicGraph
- `parse_workflow_yaml(yaml_str)` — YAML to CyclicGraph
- `workflow_to_dict(graph)` — CyclicGraph to dict

**Node Types**: entry, exit, tool, llm, agent, step, router, conditional, merge

### Multi-Modal Pipeline

**File**: `chainforge/core/multimodal.py`

Load images and files directly into Messages for vision-capable LLM providers.

**Functions**:
- `image_to_message(image_path, text, detail)` — create user Message with image
- `file_to_message(file_path, text)` — auto-detect file type
- `load_image_data(path)` — load image as base64

---

## Phase 14: Self-Optimizing Agents

### Dream/Simulation Mode

**File**: `chainforge/evolution/dream.py`

Predict tool outcomes before executing, compare with actual results, and learn from discrepancies.

**Levels**:
- `off` — no prediction
- `light` — predict tool result only (1 LLM call per tool)
- `medium` — predict + evaluate correctness (2 LLM calls)
- `deep` — full reasoning trace simulation (3+ LLM calls)

**Key Methods**:
- `record_prediction(tool_name, args, prediction, confidence)` — record prediction
- `record_actual(tool_name, args, actual)` — record and compare
- `accuracy()` — overall prediction accuracy
- `low_confidence_patterns()` — consistent failure patterns

### Technology Tree

**File**: `chainforge/evolution/tech_tree.py`

Capability tree with usage-driven unlocks, inspired by Civilization games.

**Key Types**:
- `TechTree` — tree of capabilities with unlock conditions
- `TechNode` — single capability node

**Methods**:
- `add_node(id, name, desc, requires, required_count)` — define node
- `record_usage(tool_name)` — track tool usage
- `check_unlocks()` — evaluate and unlock nodes
- `on_unlock(listener)` — register unlock callback
- `plot()` — ASCII visualization

### Multi-Generational Evolution

**File**: `chainforge/evolution/population.py`

Genetic algorithm framework that evolves optimal agent configurations.

**Key Types**:
- `AgentPopulation` — population management
- `Individual` — single agent with fitness score
- `IndividualGenome` — configurable parameters

**Operators**:
- Tournament selection
- Uniform crossover
- Gaussian mutation
- Elite preservation

---

## Phase 15: Agent Quality

### Behavioral Testing Framework

**File**: `chainforge/testing/behavior.py`

Define expected agent behavior as assertions and run deterministic tests.

**Key Types**:
- `BehaviorTest` — test case definition
- `BehaviorTestRunner` — test execution engine
- `BehaviorTestResult` — test outcome
- `BehaviorAssertion` — single assertion
- `ExpectedBehavior` — accept, reject, use_tool, no_tool, tool_sequence

**Assertion Types**: tool_called, tool_not_called, max_cost, max_llm_calls, max_tool_calls, output_contains, output_not_contains

### Performance Budget Contracts

**File**: `chainforge/middleware/budget.py`

Declare execution budgets enforced in real-time.

**Contract Fields**:
- `max_cost_usd` — maximum estimated cost
- `max_llm_calls` — maximum LLM generate() calls
- `max_tool_calls` — maximum tool executions
- `max_latency_seconds` — maximum wall-clock time
- `required_tools` — tools that must be used
- `forbidden_tools` — tools that must not be used

### Agent-as-Microservice

**File**: `chainforge/deploy.py`

One-line agent deployment with `@service` decorator.

**Functions**:
- `@service(port, path, name)` — register agent as microservice
- `serve(host, port)` — start HTTP server
- `get_registry()` — list registered agents

**Auto-generated**: REST API, OpenAPI spec, API key authentication

---

## Architecture Invariants

All Phase 11-15 features follow these principles:
1. **Protocol-based** — interfaces are protocols, not base classes
2. **Streaming-first** — all async execution returns Stream events
3. **Zero extra deps** — no new dependencies beyond pydantic + stdlib
4. **Test-first** — every feature has verification examples
5. **Self-documenting** — Pydantic models with Field descriptions

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| TimeTravelDebugger as wrapper, not middleware | Must have full access to execution state including events |
| Dream/Simulation in evolution/ | Part of the self-optimization pipeline, not core execution |
| Budget as middleware | Follows existing middleware pattern (retry, rate_limit, timeout) |
| Behavioral Testing as extension of MockLLM | MockLLM already provides deterministic execution |
| @service decorator, not subclass | Lower friction for users, consistent with @tool pattern |
