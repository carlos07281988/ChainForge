# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""ChainForge HTTP Server — REST API + SSE + thread management + auth.

Exposes:
  POST /api/v1/agents/{agent_id}/run        Run agent (JSON)
  GET  /api/v1/agents/{agent_id}/run/stream  SSE stream
  POST /api/v1/threads                       Create thread
  GET  /api/v1/threads/{thread_id}           Get thread state
  GET  /api/v1/agents                        List agents
  GET  /api/v1/health                        Health check

Features:
  - API key authentication (optional, via CHAINFORGE_API_KEY env var)
  - Thread/session management with state persistence
  - Webhook callbacks on agent completion
  - Usage tracking per API key
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query, Request, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
except ImportError:
    raise ImportError("HTTP server requires `fastapi` and `uvicorn`. Install with: pip install 'chainforge[server]'")

from pydantic import BaseModel

from chainforge._version import __version__
from chainforge.core.state import InMemoryCheckpointer, ThreadInfo
from chainforge.logging import get_logger

logger = get_logger("server")

# ── Global state ──────────────────────────────────────────────────────────

_agent_registry: dict[str, Any] = {}
_thread_store: dict[str, dict[str, Any]] = {}
_usage_store: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_tokens": 0, "total_duration_s": 0.0})
_checkpointer = InMemoryCheckpointer()

# API key auth
_API_KEY = os.environ.get("CHAINFORGE_API_KEY", "")
_WEBHOOK_TIMEOUT = 10  # seconds


def register_agent(agent_id: str, agent: Any, description: str = "",
                   webhook_url: str | None = None) -> None:
    """Register an agent for HTTP access.

    Args:
        agent_id: Unique identifier (used in URL paths).
        agent: Any ChainForge agent.
        description: Human-readable description.
        webhook_url: Optional URL to POST results upon agent completion.
    """
    _agent_registry[agent_id] = {
        "agent": agent,
        "description": description or str(type(agent).__name__),
        "webhook_url": webhook_url,
    }


def get_registry() -> dict[str, Any]:
    return _agent_registry


# ── Auth dependency ────────────────────────────────────────────────────────

async def verify_api_key(request: Request) -> str | None:
    """Dependency: verify API key if CHAINFORGE_API_KEY is set."""
    if not _API_KEY:
        return None  # Auth disabled
    api_key = request.headers.get("X-API-Key", "")
    if api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


# ── Request/Response models ───────────────────────────────────────────────

class RunRequest(BaseModel):
    prompt: str = ""
    context: dict[str, Any] | None = None
    response_model: str | None = None
    thread_id: str | None = None


class RunResponse(BaseModel):
    output: str = ""
    duration_s: float = 0.0
    tool_calls: int = 0
    events: list[dict] = []
    thread_id: str | None = None


class AgentInfo(BaseModel):
    id: str = ""
    description: str = ""
    tools: list[str] = []
    system_prompt: str | None = None
    agent_type: str = ""
    webhook_url: str | None = None


class AgentListInfo(BaseModel):
    id: str = ""
    agent_type: str = ""
    tools: list[str] = []
    description: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = __version__
    agents: int = 0


class ThreadCreateRequest(BaseModel):
    agent_id: str = ""
    metadata: dict[str, Any] = {}


class ThreadResponse(BaseModel):
    thread_id: str
    agent_id: str
    created_at: float
    updated_at: float
    message_count: int = 0
    metadata: dict[str, Any] = {}


class UsageResponse(BaseModel):
    api_key: str = ""
    total_requests: int = 0
    total_tokens: int = 0
    total_duration_s: float = 0.0


# ── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="ChainForge API",
    description="HTTP interface for ChainForge agents with auth, threads, and webhooks",
    version=__version__,
    dependencies=[Depends(verify_api_key)] if _API_KEY else [],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "server_static"


# ── Helpers ────────────────────────────────────────────────────────────────

def _list_agent_tools(agent) -> list[str]:
    if hasattr(agent, "_all_tools"):
        return [t.spec.name for t in agent._all_tools()]
    if hasattr(agent, "tools"):
        return [t.spec.name if hasattr(t, "spec") else str(t) for t in agent.tools]
    return []


def _get_agent(agent_id: str) -> tuple[Any, dict]:
    if agent_id not in _agent_registry:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Registered: {list(_agent_registry.keys())}",
        )
    entry = _agent_registry[agent_id]
    return entry["agent"], entry


def _track_usage(api_key: str | None, tokens: int = 0, duration_s: float = 0.0) -> None:
    if api_key:
        key = api_key[:8] + "..." if len(api_key) > 8 else api_key
        _usage_store[key]["count"] += 1
        _usage_store[key]["total_tokens"] += tokens
        _usage_store[key]["total_duration_s"] += duration_s


async def _fire_webhook(agent_id: str, thread_id: str | None, output: str, duration_s: float) -> None:
    """Fire webhook callback if agent has webhook_url configured."""
    entry = _agent_registry.get(agent_id)
    if not entry:
        return
    webhook_url = entry.get("webhook_url")
    if not webhook_url:
        return

    payload = {
        "event": "agent.completed",
        "agent_id": agent_id,
        "thread_id": thread_id,
        "output": output,
        "duration_s": duration_s,
        "timestamp": time.time(),
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
            logger.info(f"Webhook to {webhook_url}: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Webhook to {webhook_url} failed: {e}")


# ── Health & Agent Info ────────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    return HealthResponse(version=__version__, agents=len(_agent_registry))


@app.get("/api/v1/agents")
async def list_agents():
    result = []
    for agent_id, entry in _agent_registry.items():
        agent = entry["agent"]
        result.append(AgentListInfo(
            id=agent_id,
            agent_type=type(agent).__name__,
            tools=_list_agent_tools(agent),
            description=entry.get("description", ""),
        ))
    return result


@app.get("/api/v1/agents/{agent_id}", response_model=AgentInfo)
async def agent_info(agent_id: str):
    agent, entry = _get_agent(agent_id)
    tools = []
    if hasattr(agent, "_all_tools"):
        tools = [t.spec.name for t in agent._all_tools()]
    elif hasattr(agent, "tools"):
        tools = [t.spec.name if hasattr(t, "spec") else str(t) for t in agent.tools]
    return AgentInfo(
        id=agent_id,
        description=entry.get("description", ""),
        tools=tools,
        system_prompt=getattr(agent, "system_prompt", None),
        agent_type=type(agent).__name__,
        webhook_url=entry.get("webhook_url"),
    )


# ── Thread Management ──────────────────────────────────────────────────────

@app.post("/api/v1/threads", response_model=ThreadResponse)
async def create_thread(request: ThreadCreateRequest):
    """Create a new thread/session for an agent."""
    if request.agent_id and request.agent_id not in _agent_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{request.agent_id}' not found")

    thread_id = str(uuid.uuid4())
    now = time.time()
    thread = {
        "thread_id": thread_id,
        "agent_id": request.agent_id,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "state": {},
        "metadata": request.metadata,
    }
    _thread_store[thread_id] = thread
    logger.info(f"Thread created: {thread_id} for agent {request.agent_id}")
    return ThreadResponse(
        thread_id=thread_id,
        agent_id=request.agent_id,
        created_at=now,
        updated_at=now,
        metadata=request.metadata,
    )


@app.get("/api/v1/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: str):
    """Get thread/session state."""
    thread = _thread_store.get(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    return ThreadResponse(
        thread_id=thread["thread_id"],
        agent_id=thread["agent_id"],
        created_at=thread["created_at"],
        updated_at=thread["updated_at"],
        message_count=thread.get("message_count", 0),
        metadata=thread.get("metadata", {}),
    )


@app.delete("/api/v1/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread."""
    if thread_id not in _thread_store:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    _thread_store.pop(thread_id)
    return {"status": "deleted", "thread_id": thread_id}


@app.get("/api/v1/threads")
async def list_threads(agent_id: str | None = None):
    """List all threads, optionally filtered by agent_id."""
    threads = list(_thread_store.values())
    if agent_id:
        threads = [t for t in threads if t.get("agent_id") == agent_id]
    return [
        ThreadResponse(
            thread_id=t["thread_id"],
            agent_id=t.get("agent_id", ""),
            created_at=t["created_at"],
            updated_at=t["updated_at"],
            message_count=t.get("message_count", 0),
            metadata=t.get("metadata", {}),
        )
        for t in sorted(threads, key=lambda x: x["updated_at"], reverse=True)
    ]


# ── Usage Tracking ─────────────────────────────────────────────────────────

@app.get("/api/v1/usage", response_model=UsageResponse)
async def get_usage(api_key: str | None = None):
    """Get usage statistics for an API key."""
    key = api_key or "unauthenticated"
    if len(key) > 8:
        key = key[:8] + "..."
    stats = _usage_store.get(key, {"count": 0, "total_tokens": 0, "total_duration_s": 0.0})
    return UsageResponse(
        api_key=key,
        total_requests=stats["count"],
        total_tokens=stats["total_tokens"],
        total_duration_s=stats["total_duration_s"],
    )


# ── Agent Run ──────────────────────────────────────────────────────────────

@app.post("/api/v1/agents/{agent_id}/run", response_model=RunResponse)
async def run_agent(agent_id: str, request: RunRequest, api_key: str | None = Depends(verify_api_key)):
    """Run an agent and return the full result as JSON.

    Supports thread_id for session persistence.
    """
    agent, _ = _get_agent(agent_id)
    start = time.monotonic()

    # Thread management
    thread_id = request.thread_id
    if thread_id and thread_id in _thread_store:
        thread = _thread_store[thread_id]
        thread["updated_at"] = time.time()
        thread["message_count"] += 1
    elif thread_id and thread_id not in _thread_store:
        # Auto-create thread
        now = time.time()
        _thread_store[thread_id] = {
            "thread_id": thread_id,
            "agent_id": agent_id,
            "created_at": now,
            "updated_at": now,
            "message_count": 1,
            "state": {},
            "metadata": {},
        }

    stream = await agent.run(request.prompt or "Hello", context=request.context)
    text_parts: list[str] = []
    all_events: list[dict] = []
    tool_call_count = 0
    total_tokens = 0

    async for event in stream:
        ev = {"type": event.type.value, "content": event.content, "data": event.data}
        all_events.append(ev)
        if event.type.value == "text" and event.content:
            text_parts.append(event.content)
        if event.type.value == "tool_call":
            tool_call_count += 1
        if event.data and "usage" in (event.data or {}):
            usage = event.data.get("usage" , {})
            if isinstance(usage, dict):
                total_tokens += usage.get("total_tokens", 0)

    duration = time.monotonic() - start
    output = "".join(text_parts)

    # Track usage
    _track_usage(api_key, total_tokens, duration)

    # Fire webhook
    asyncio.ensure_future(_fire_webhook(agent_id, thread_id, output, duration))

    return RunResponse(
        output=output,
        duration_s=round(duration, 3),
        tool_calls=tool_call_count,
        events=all_events,
        thread_id=thread_id,
    )


@app.get("/api/v1/agents/{agent_id}/run/stream")
async def stream_agent(
    agent_id: str,
    prompt: str = Query(default="Hello", description="Prompt for the agent"),
    thread_id: str | None = Query(default=None, description="Optional thread ID"),
    api_key: str | None = Depends(verify_api_key),
):
    """Run an agent and stream events via Server-Sent Events (SSE)."""
    agent, _ = _get_agent(agent_id)

    async def event_generator() -> AsyncIterator[str]:
        start = time.monotonic()
        stream = await agent.run(prompt)

        async for event in stream:
            data = {
                "type": event.type.value,
                "content": event.content,
                "data": event.data,
            }
            yield f"event: {event.type.value}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            # Track usage from events
            if event.data and "usage" in (event.data or {}):
                usage = event.data.get("usage", {})
                if isinstance(usage, dict):
                    _track_usage(api_key, usage.get("total_tokens", 0), 0)

        duration = time.monotonic() - start
        yield f"event: done\ndata: {json.dumps({'duration_s': round(duration, 3), 'thread_id': thread_id})}\n\n"

        # Fire webhook
        text_parts: list[str] = []
        # Stream already consumed; re-run isn't practical here
        asyncio.ensure_future(_fire_webhook(agent_id, thread_id, "(streamed)", duration))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Eval ───────────────────────────────────────────────────────────────────

@app.post("/api/v1/eval/run")
async def run_eval(request: Request):
    """Run evaluation on a registered agent."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    agent_id = body.get("agent_id", "")
    if agent_id not in _agent_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    agent, _ = _get_agent(agent_id)
    cases_data = body.get("cases", [])
    from chainforge.eval.case import EvalCase
    from chainforge.eval.suite import EvalSuite
    from chainforge.eval.runner import EvalRunner
    from chainforge.eval.report import EvalReport
    cases = [EvalCase(**c) for c in cases_data]
    suite = EvalSuite(name=body.get("suite_name", "api-run"), cases=cases)
    runner = EvalRunner(agent, suite, name=agent_id)
    result = await runner.run_all()
    report = EvalReport(result)
    return JSONResponse(content=json.loads(report.to_json()))


# ── DAG API ────────────────────────────────────────────────────────────────

@app.get("/api/v1/dag/stream")
async def stream_dag(dag: str = Query(..., description="JSON-encoded DAG definition")):
    """Execute a DAG defined via query parameter and stream events."""
    try:
        dag_data = json.loads(dag)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid DAG JSON")

    from chainforge.core.graph import DAG as ChainForgeDAG, GraphNodeType

    cf_dag = ChainForgeDAG(name=dag_data.get("name", "custom"))
    for n in dag_data.get("nodes", []):
        nt = n.get("type", "step")
        type_map = {"step": GraphNodeType.step, "input": GraphNodeType.entry,
                     "output": GraphNodeType.exit, "router": GraphNodeType.router,
                     "merge": GraphNodeType.merge}
        label = n.get("label", n.get("id", "unknown"))

        def _mk_fn(lbl, ntype):
            def fn(x=None):
                pf = f"[{ntype.upper()} {lbl}]"
                if x is not None:
                    return f"{pf} {x}"
                return pf
            return fn

        cf_dag.add_node(n["id"], fn=_mk_fn(label, nt),
                        node_type=type_map.get(nt, GraphNodeType.step),
                        description=label)

    for e in dag_data.get("edges", []):
        cf_dag.add_edge(e["source"], e["target"])

    input_data = dag_data.get("input", "Start")

    async def event_generator():
        stream = cf_dag.run(input_data)
        async for event in stream:
            data = {"type": event.type.value, "content": event.content, "data": event.data}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Dashboard static routes ────────────────────────────────────────────────

@app.get("/static/{path:path}")
async def serve_static(path: str):
    file_path = STATIC_DIR / path
    if not file_path.exists() or file_path.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    ext = file_path.suffix
    ct_map = {".css": "text/css", ".js": "text/javascript", ".html": "text/html",
               ".png": "image/png", ".svg": "image/svg+xml"}
    return Response(content=file_path.read_bytes(), media_type=ct_map.get(ext, "application/octet-stream"))


@app.get("/dashboard")
async def dashboard_index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


@app.get("/dashboard/agent-run")
async def dashboard_agent_run():
    page = STATIC_DIR / "agent-run.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


@app.get("/dashboard/dag-editor")
async def dashboard_dag_editor():
    page = STATIC_DIR / "dag-editor.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


# ── Debugger API ───────────────────────────────────────────────────────────

_debugger_api = None


def get_debugger_api():
    global _debugger_api
    if _debugger_api is None:
        from chainforge.debugger import DebuggerAPI
        _debugger_api = DebuggerAPI()
    return _debugger_api


@app.on_event("startup")
async def register_debugger():
    api = get_debugger_api()
    app.include_router(api.router, prefix="/api/v1/debug")

# ── Trace Viewer API ────────────────────────────────────────────────────────

_trace_store = None


def _get_trace_store():
    global _trace_store
    if _trace_store is None:
        from chainforge.tracing.store import TraceStore
        _trace_store = TraceStore()
    return _trace_store


@app.get("/api/v1/traces")
async def list_traces(limit: int = 20, offset: int = 0, agent_id: str | None = None):
    """List agent execution traces."""
    store = _get_trace_store()
    return await store.list_traces(limit=limit, offset=offset, agent_id=agent_id)


@app.get("/api/v1/traces/stats")
async def trace_stats():
    """Get aggregate trace statistics."""
    store = _get_trace_store()
    return await store.get_stats()


@app.get("/api/v1/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a single trace with all spans."""
    store = _get_trace_store()
    trace = await store.get_trace(trace_id)
    if trace is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return trace

# ── Debugger Dashboard route ──────────────────────────────────────────────

@app.get("/dashboard/debugger")
async def dashboard_debugger():
    page = STATIC_DIR / "debugger.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))

