# ChainForge × Google ADK & MS Agent Framework Integration

> Technical design document for the integration of features from Google ADK
> and Microsoft Agent Framework into ChainForge. 2026-07.

---

## Overview

This document describes the six modules integrated from **Google's Agent Development Kit (ADK)**
and **Microsoft Agent Framework**, their design rationale, and how they fit into ChainForge's
existing architecture.

### Sources

| Feature | Primary Source | Secondary Source |
|---------|:-------------:|:----------------:|
| Artifact Management | Google ADK (rich media artifacts) | — |
| InvocationContext | Google ADK (InvocationContext) | MS Agent (AgentClient context) |
| Tool & Agent Lifecycle Hooks | Google ADK (before_tool/after_tool) | — |
| Structured Activity Logging | Google ADK (ActivityLog) | — |
| Thread/Session Manager | MS Agent Framework (ConversationId/TurnId) | Google ADK (session state) |
| WebSearch Tool | Google ADK (WebSearch grounding) | MS Agent (Bing grounding) |

---

## Module Details

### 1. ArtifactStore — `chainforge/core/artifact.py`

**Design Inspiration:** Google ADK treats generated files, images, code, and data
as first-class "artifacts" with stable IDs, MIME types, and metadata. ChainForge
previously only had `FileLoader` for reading local files — there was no storage,
search, or lifecycle management.

**Key Design Decisions:**
- **Bytes-first storage:** Artifacts store raw `bytes` internally; `text` is a
  computed property. This makes the system format-agnostic.
- **Type auto-detection:** `Artifact._detect_type()` infers the artifact category
  from MIME type and file extension, enabling type-based search without explicit
  tagging.
- **Session scoping:** `ArtifactStore.session_scope()` creates a filtered view
  without duplicating data, matching the multi-tenant pattern used in Google ADK.
- **Optional disk persistence:** When `persist_dir` is set, artifacts are
  automatically written with adjacent `.meta.json` files for crash recovery.

**Integration Points:**
- `Artifact.to_message_part()` → `ContentPart` for multi-modal LLM messages
- `ScopedArtifactStore` → fits with `InvocationContext.session_id` for session isolation

---

### 2. InvocationContext — `chainforge/core/context.py`

**Design Inspiration:** Both Google ADK and MS Agent Framework carry a standardized
context object through the agent execution pipeline. ChainForge previously passed
a bare `dict[str, Any]` with no schema or validation.

**Key Design Decisions:**
- **Pydantic schema** for validation and static analysis.
- **Two-way conversion:** `to_dict()` / `from_dict()` bridges between the typed
  `InvocationContext` and the untyped `dict` that Agent.run() accepts as `context`.
- **`_invocation_context` sentinel key:** The full object is stored in the dict
  under a private key so `get_invocation_context()` can reconstruct it without
  ambiguity.
- **`with_context()` helper:** Provides a lightweight API for ad-hoc usage.

**Integration Points:**
- Passed as `context` parameter in `Agent.run()`
- Available to `ToolHook.before_run()` / `AgentHook.on_start()` via `ctx` dict
- `session_id` links to `ThreadManager` and `ActivityLogger.session_id`

---

### 3. Tool & Agent Lifecycle Hooks — `chainforge/core/hooks.py`

**Design Inspiration:** Google ADK provides `before_tool` / `after_tool` decorators
that can modify behavior (skipping execution, transforming results). ChainForge
had `Callback` (observational only) and `BaseTool._run` / `_arun` (tool-level).
Neither allowed third-party intervention in the execution flow.

**Key Design Decisions:**
- **Dual inheritance:** `LoggingHook` extends both `ToolHook` and `AgentHook`,
  sharing one implementation across both hook types.
- **`None` return semantics:** `before_run()` returning `None` signals "skip this
  tool" — a pattern used in Google ADK for conditional execution.
- **Hook chain:** Multiple hooks execute in registration order; each receives the
  output of the previous hook (decorator pattern).
- **Complements Callback:** `ToolHook`/`AgentHook` can modify behavior; `Callback`
  observes only. This separation follows ChainForge's principle of separating
  concerns (middleware → modify stream, hooks → modify behavior, callbacks → observe).

**Built-in Implementations:**
| Hook | Type | Purpose |
|------|------|---------|
| `LoggingHook` | Tool + Agent | Structured event logging |
| `MetricsHook` | Agent | Execution timing and event counts |
| `TimingHook` | Tool | Per-tool execution time with slow-tool warnings |

---

### 4. ActivityLogger — `chainforge/core/activity.py`

**Design Inspiration:** Google ADK's `ActivityLog` provides categorized,
structured, queryable activity logs for agent debugging and monitoring.
ChainForge had `logging.py` (stdlib wrapping) and `LoggingCallback` but no
structured, queryable log system.

**Key Design Decisions:**
- **Dot-notation categories:** `"tool.search"`, `"agent.run"`, etc. Support
  glob-based querying via `fnmatch` (e.g., `"tool.*"`).
- **Specialized methods:** `tool_call()` / `tool_result()` create structured
  entries with `tool_name`, `duration_ms`, and `payload` fields.
- **In-memory ring buffer:** Default 10K events; FIFO eviction. No external
  dependencies.
- **Export:** `export_json()` for integration with external log aggregators.

**Integration Points:**
- `session_id` and `invocation_id` align with `InvocationContext`
- `tool_name` aligns with `ToolHook.before_run()` name parameter

---

### 5. ThreadManager — `chainforge/core/thread.py`

**Design Inspiration:** MS Agent Framework's `ConversationId` / `TurnId` system
provides structured multi-turn conversation management with thread isolation.
ChainForge had `StateTracker` / `Checkpointer` for state persistence but no
conversation-level abstraction.

**Key Design Decisions:**
- **In-memory by default:** Thread data lives in memory for simplicity; the
  `Checkpointer` pattern (from `core/state.py`) handles persistence.
- **Auto-prune:** `max_messages_per_thread` prevents unbounded memory growth.
- **Turn tracking:** `start_turn()` / `end_turn()` with `duration_ms` enables
  per-turn observability.
- **Thread metadata:** `title`, `user_id`, `agent_id`, `tags`, `custom` for
  categorization and filtering.

**Integration Points:**
- `thread_id` maps to `Agent.run(thread_id=...)` and `Checkpointer` threads
- `user_id` aligns with `InvocationContext.user_id`

---

### 6. WebSearch Tool — `chainforge/tools/websearch.py`

**Design Inspiration:** Google ADK includes a built-in `WebSearch` tool with
multiple search backends and result grounding. MS Agent Framework provides
Bing search grounding. ChainForge had no built-in search capability.

**Key Design Decisions:**
- **DuckDuckGo as default:** No API key required, works out of the box.
- **Multiple backends:** DuckDuckGo, SerpAPI, Bing with unified interface.
- **`web_fetch` companion:** Extracts visible text from URLs using regex-based
  HTML-to-text conversion (no BeautifulSoup dependency).
- **Environment variable fallback:** `SERPAPI_API_KEY` / `BING_API_KEY` can be
  set without hardcoding keys in code.

**Backend Comparison:**
| Backend | Auth | Cost | Result Quality |
|---------|------|------|---------------|
| DuckDuckGo | None | Free | Good (HTML parsing) |
| SerpAPI | API key | Paid ($0.01/search) | Excellent (structured JSON) |
| Bing | API key | Paid ($7/1K calls) | Excellent (Microsoft) |

---

## Architecture Integration

```
User Request
     │
     ▼
┌──────────────────────────────────────────────┐
│  InvocationContext (session, user, trace)     │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│  ThreadManager (message history, turns)       │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│  Agent (with hooks)                           │
│  ┌──────────────┐  ┌───────────────────┐     │
│  │ AgentHook    │  │ ToolHook chain    │     │
│  │ on_start()   │  │ before_run() →  ──┤     │
│  │ on_step()    │  │ execute tool    ←─┤     │
│  │ on_error()   │  │ after_run()       │     │
│  │ on_finish()  │  │ on_error()        │     │
│  └──────────────┘  └───────────────────┘     │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│  ActivityLogger (structured logs)             │
│  info(), tool_call(), warning(), error()      │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│  ArtifactStore (files, images, data)          │
│  save(), get(), search(), prune()             │
└──────────────────────────────────────────────┘

Tools:
  web_search()  web_fetch()  (DuckDuckGo / SerpAPI / Bing)
```

---

## Comparison: ChainForge Feature Matrix

| Feature | Before | After | Source |
|---------|--------|-------|--------|
| Artifact management | `FileLoader` (read-only) | `ArtifactStore` (CRUD + search + prune) | Google ADK |
| Execution context | Bare `dict[str, Any]` | Typed `InvocationContext` with schema | Google ADK + MS |
| Tool hooks | `BaseTool._run` / `_arun` only | `ToolHook.before_run/after_run` chain | Google ADK |
| Agent hooks | `Callback` (observe only) | `AgentHook.on_start/step/error/finish` | Google ADK |
| Activity logging | `logging.info()` (unstructured) | `ActivityLogger` (queryable, categorized) | Google ADK |
| Thread management | `thread_id` param (bare) | `ThreadManager` (CRUD + history + turns) | MS Framework |
| Web search | Manual `urllib` in tool code | `web_search()` with 3 backends | Google ADK |

---

## Future Extensions

1. **ArtifactStore persistence backends:** SQLite / S3 / GCS.
2. **ThreadManager persistence:** Integrate with existing `Checkpointer` protocol.
3. **ActivityLogger streaming:** Real-time activity feed via Server-Sent Events.
4. **Hook composition:** Middleware-style hook chain with error propagation.
5. **WebSearch caching:** Deduplicate recent searches with `LLMResponseCache`.
