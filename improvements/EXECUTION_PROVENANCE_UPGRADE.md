# Execution Provenance Graph — Upgrade

> Phase 19: Upgrade TimeTravelDebugger with full causal tracing and provenance visualization.
> Status: 📋 Planned | Priority: P1 | Effort: 10-14 days

---

## Motivation

TimeTravelDebugger records *what* happened. Provenance Graph answers *why* it happened —
which input caused which output, which decision led to which tool call, and what the full
causal chain was.

---

## Causal Tracing Model

```
User: "What's the weather in Beijing?"
  │
  ▼
LLM Call #1 (gpt-4o, system prompt + user msg)
  │
  ├── tool_call: get_weather(city="Beijing") ←── caused_by: LLM Call #1
  │       │
  │       └── tool_result: "Beijing: 28°C, Sunny" ←── caused_by: get_weather
  │
  └── LLM Call #2 (gpt-4o, messages + tool result) ←── caused_by: tool_result
        │
        └── text: "The weather in Beijing is 28°C..." ←── caused_by: LLM Call #2
```

Each node records:
- `id`, `type` (llm_call, tool_call, tool_result, state_transition, user_input)
- `caused_by` — parent node ID
- `causal_group` — execution context (iteration, agent_id in multi-agent)
- `data` — payload
- `timestamp`, `duration_ms`

---

## API

```python
from chainforge.core.provenance import ProvenanceTracker

tracker = ProvenanceTracker()

# Automatically wraps agent execution
debugger = TimeTravelDebugger(agent, provenance=True)
stream = await debugger.run("What's the weather?")

# Query causal chains
chain = debugger.provenance.trace_decision("tool_result_1")
# Returns:
#   tool_result_1 ← get_weather ← LLM Call #1 ← user_input

# Full provenance graph
graph = debugger.provenance.graph()
# Returns DirectedGraph of all causal relationships

# Critical path analysis
path = debugger.provenance.critical_path("final_output")
# Returns the minimal set of nodes that influenced the final output
```

---

## Storage

Provenance data is stored alongside checkpoints in SQLite:

```sql
CREATE TABLE provenance_nodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    node_type TEXT NOT NULL,        -- llm_call, tool_call, tool_result, etc.
    caused_by TEXT,                 -- parent node ID (NULL for root)
    causal_group TEXT,              -- iteration number or agent_id
    data JSON NOT NULL,
    timestamp REAL NOT NULL,
    duration_ms REAL
);

CREATE INDEX idx_prov_session ON provenance_nodes(session_id);
CREATE INDEX idx_prov_caused_by ON provenance_nodes(caused_by);
```

---

## Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `chainforge/core/provenance.py` | ProvenanceTracker, ProvenanceNode |
| 2 | `chainforge/core/provenance_store.py` | SQLite storage for provenance data |
| 3 | `chainforge/core/provenance_query.py` | trace_decision(), critical_path(), graph() |
| 4 | Integration into TimeTravelDebugger | `provenance=True` flag |
| 5 | REST API | `/api/v1/debug/{session}/provenance` |
