# Agent Visual Debugger UI

> Phase 17: Web-based visual debugger for TimeTravelDebugger.
> Status: 📋 Planned | Priority: P0 | Effort: 14-21 days

---

## Motivation

LangChain has LangGraph Studio, but it's a hosted service. ChainForge's
TimeTravelDebugger provides the most advanced agent debugging capabilities
in any open-source framework — provenance tracing, checkpoint replay, branch
comparison — but only through a Python API. A web UI makes these capabilities
accessible to all developers regardless of their familiarity with the Python API.

**Target Audience:** Agent developers debugging complex multi-step behaviors

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│               Debugger UI (React)                 │
│                                                   │
│  ┌─────────────┐  ┌──────────────┐               │
│  │ Timeline     │  │ State        │               │
│  │ (event       │  │ Inspector    │               │
│  │  waterfall)  │  │ (messages,   │               │
│  │              │  │  tool results)│               │
│  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                        │
│  ┌──────▼─────────────────▼───────┐               │
│  │ Control Bar                    │               │
│  │ [⏸ Pause] [▶ Step] [⏮ Replay] │               │
│  │ [🔀 Branch] [📋 Breakpoints]   │               │
│  └──────┬─────────────────────────┘               │
└─────────┼──────────────────────────────────────────┘
          │ WebSocket (ALDP protocol)
          ▼
┌──────────────────────────────────────────────────┐
│              ChainForge Server (FastAPI)           │
│                                                    │
│  /api/v1/debug/* — REST endpoints                 │
│  /ws/debug — WebSocket for live streaming         │
│                                                    │
│  ALDPEventBus — transforms agent events → WS msgs │
└─────────────────────┬──────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────┐
│         Agent + TimeTravelDebugger                  │
│  record → checkpoint → provenance → replay         │
└────────────────────────────────────────────────────┘
```

---

## API Design

### REST Endpoints

```
GET  /api/v1/debug/sessions                     — list debug sessions
POST /api/v1/debug/sessions                     — start new debug session
GET  /api/v1/debug/sessions/{id}                — get session details
GET  /api/v1/debug/sessions/{id}/checkpoints    — list checkpoints
GET  /api/v1/debug/sessions/{id}/checkpoints/{ckp}  — get checkpoint state
POST /api/v1/debug/sessions/{id}/replay         — replay from checkpoint
POST /api/v1/debug/sessions/{id}/branch         — fork at checkpoint
GET  /api/v1/debug/sessions/{id}/provenance     — get provenance graph
GET  /api/v1/debug/sessions/{id}/events         — get event stream
```

### WebSocket Messages (ALDP)

```json
// Server → Client: Event
{
  "type": "event",
  "event_type": "tool_call" | "llm_call" | "state_transition" | "error",
  "data": { ... },
  "timestamp": 1234567890,
  "checkpoint_id": "ckp_..."
}

// Client → Server: Command
{
  "type": "command",
  "command": "pause" | "resume" | "step" | "replay",
  "params": { "checkpoint_id": "ckp_..." }
}
```

---

## UI Component Tree

```
DebuggerApp
├── SessionList (sidebar)
│   ├── SessionCard (name, duration, event count)
│   └── NewSessionButton
├── Timeline (center)
│   ├── TimelineHeader (controls, search)
│   ├── EventList
│   │   ├── LLMEvent (model, tokens, duration)
│   │   ├── ToolCallEvent (tool name, args preview)
│   │   ├── ToolResultEvent (tool name, result preview)
│   │   ├── StateTransitionEvent (from → to)
│   │   └── ErrorEvent (error message)
│   └── CheckpointMarkers (vertical markers on timeline)
├── Inspector (right panel)
│   ├── MessageView (full message contents)
│   ├── ToolResultView (full result, syntax highlighted)
│   ├── StateView (current agent state)
│   └── ProvenanceView (causal chain graph)
└── ControlBar (bottom)
    ├── PlayPauseButton
    ├── StepOverButton
    ├── StepIntoButton
    ├── ReplayButton
    ├── BranchButton
    └── BreakpointEditor
```

---

## Data Flow

```
1. User clicks "New Session"
   → POST /api/v1/debug/sessions
   → Server creates Agent + TimeTravelDebugger
   → Returns session ID

2. Agent starts executing
   → TimeTravelDebugger records checkpoints
   → ALDPEventBus transforms events → WebSocket messages
   → UI Timeline appends events in real-time

3. User clicks pause
   → WS: {"command": "pause"}
   → Server pauses agent at next checkpoint
   → UI shows current state

4. User inspects a checkpoint
   → GET /api/v1/debug/sessions/{id}/checkpoints/{ckp}
   → Server returns full state (messages, tool results, context)
   → Inspector panel displays formatted state

5. User clicks "Branch"
   → POST /api/v1/debug/sessions/{id}/branch?checkpoint={ckp}&modified_prompt=...
   → Server forks execution, creates new branch session
   → UI opens branch in new tab
```

---

## Implementation Plan

### Phase 1: Backend (5-7 days)

| Step | Files | Description |
|------|-------|-------------|
| 1.1 | `chainforge/debugger/aldp_bus.py` | ALDPEventBus — transforms StreamEvents → WS messages |
| 1.2 | `chainforge/debugger/session.py` | DebugSession — manages one debug session lifecycle |
| 1.3 | `chainforge/debugger/api.py` | REST + WS endpoints for debugger |
| 1.4 | `chainforge/server.py` | Register debugger routes, serve static UI |

### Phase 2: Frontend (7-10 days)

| Step | Description |
|------|-------------|
| 2.1 | React app scaffold + WebSocket connection |
| 2.2 | Timeline component with virtual scrolling |
| 2.3 | Event components (LLM, ToolCall, ToolResult, State, Error) |
| 2.4 | Inspector panel (Message, ToolResult, State, Provenance views) |
| 2.5 | Control bar (pause/step/replay/branch) |
| 2.6 | Session list + new session flow |
| 2.7 | Breakpoint editor + provenance graph |

### Phase 3: Polish (3-5 days)

| Step | Description |
|------|-------------|
| 3.1 | Search & filter events |
| 3.2 | Branch comparison (diff view) |
| 3.3 | Export/import debug sessions |
| 3.4 | Performance optimization (large sessions) |

---

## Dependencies

- **Existing:** `chainforge/core/time_travel.py` (TimeTravelDebugger)
- **Existing:** `chainforge/core/debugger.py` (StepDebugger)
- **Existing:** `chainforge/aldp/` (Agent Live Debug Protocol)
- **Existing:** `chainforge/server.py` (FastAPI server)
- **New:** React + TypeScript (frontend), served as static files

---

## Success Criteria

1. User can start a debug session from the browser
2. Timeline shows all agent events in real-time
3. User can pause execution and inspect full state
4. User can replay from any checkpoint
5. User can fork a branch at any checkpoint
6. User can compare two branches side-by-side
7. Session persists across page refreshes
