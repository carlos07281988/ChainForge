# Natural Language → Agent Compiler

> Phase 18: Describe agent workflows in natural language, ChainForge compiles them into CyclicGraphs.
> Status: 📋 Planned | Priority: P0 | Effort: 14-21 days

---

## Motivation

Building agent workflows currently requires Python or YAML expertise. This feature
lowers the barrier to entry by letting any user describe their desired agent behavior
in plain language. ChainForge becomes the first framework where you can "prompt an agent
into existence."

---

## Architecture

```
User Input: "search web, if results found summarize, otherwise generate"
     │
     ▼
┌──────────────────────────────────────────────────┐
│              NL Compiler Pipeline                 │
│                                                    │
│  ┌──────────────┐    ┌──────────────────┐         │
│  │ Step 1:      │    │ Step 2:           │         │
│  │ NL → Intent  │───▶│ Intent → Graph IR │         │
│  │ (LLM parses  │    │ (structured       │         │
│  │  intent +    │    │  representation)  │         │
│  │  constraints)│    │                   │         │
│  └──────────────┘    └────────┬──────────┘         │
│                               │                    │
│  ┌────────────────────────────▼──────────┐         │
│  │ Step 3: Graph IR → CyclicGraph        │         │
│  │ (code generation + validation)         │         │
│  └────────────────┬──────────────────────┘         │
└───────────────────┼──────────────────────────────────┘
                    │
                    ▼
            Executable CyclicGraph
     entry → search → [has_results?] → summarize → exit
                       [no results] → generate → exit
```

---

## Intent Schema

The LLM parses natural language into a structured intent:

```json
{
  "name": "search_and_summarize",
  "description": "Search web and summarize or generate",
  "nodes": [
    {"id": "entry", "type": "entry"},
    {"id": "search", "type": "tool", "tool": "web_search", "description": "Search the web"},
    {"id": "has_results", "type": "conditional", "description": "Check if results exist"},
    {"id": "summarize", "type": "llm", "prompt": "Summarize the search results"},
    {"id": "generate", "type": "llm", "prompt": "Generate a response from knowledge"},
    {"id": "exit", "type": "exit"}
  ],
  "edges": [
    {"source": "entry", "target": "search"},
    {"source": "search", "target": "has_results"},
    {"source": "has_results", "target": "summarize", "condition": "has_results"},
    {"source": "has_results", "target": "generate", "condition": "no_results"},
    {"source": "summarize", "target": "exit"},
    {"source": "generate", "target": "exit"}
  ]
}
```

---

## Implementation Plan

### Phase 1: Parser (7-10 days)

| Step | File | Description |
|------|------|-------------|
| 1.1 | `chainforge/compiler/parser.py` | LLM-based natural language → intent schema |
| 1.2 | `chainforge/compiler/schema.py` | IntentSchema, NodeDef, EdgeDef models |
| 1.3 | `chainforge/compiler/templates.py` | Workflow templates for common patterns |
| 1.4 | `chainforge/compiler/validator.py` | Validate generated intent schema |

### Phase 2: Codegen (5-7 days)

| Step | File | Description |
|------|------|-------------|
| 2.1 | `chainforge/compiler/codegen.py` | IntentSchema → CyclicGraph Python code |
| 2.2 | `chainforge/compiler/yamlgen.py` | IntentSchema → YAML workflow |
| 2.3 | `chainforge/compiler/compiler.py` | Unified compiler interface |

### Phase 3: CLI + UX (3-5 days)

| Step | Description |
|------|-------------|
| 3.1 | `chainforge compile "..."` CLI command |
| 3.2 | `chainforge compile --interactive` step-by-step mode |
| 3.3 | Error reporting + suggestions |
