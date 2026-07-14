# Copyright 2024 ChainForge Contributors
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
"""ChainForge HTTP Server — 通过 REST API 和 SSE 流式暴露 Agent 能力。

以 FastAPI 提供以下端点:
  POST /api/v1/agents/{agent_id}/run        运行 Agent (返回 JSON)
  GET  /api/v1/agents/{agent_id}/run/stream  SSE 流式运行
  GET  /api/v1/agents/{agent_id}             Agent 信息
  GET  /api/v1/health                        健康检查

启动:
  chainforge serve --port 8000
或:
  python -m chainforge.server
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import json
import time
from collections.abc import AsyncIterator
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
except ImportError:
    raise ImportError(
        "HTTP server requires `fastapi` and `uvicorn`. Install with: pip install 'chainforge[server]'"
    )

from pydantic import BaseModel

from chainforge._version import __version__

# ── Global agent registry ─────────────────────────────────────────────────────
_agent_registry: dict[str, Any] = {}


def register_agent(agent_id: str, agent: Any, description: str = "") -> None:
    """Register an agent for HTTP access.

    Args:
        agent_id: Unique identifier (used in URL paths).
        agent: Any ChainForge agent (Agent, ReActAgent, PlanAndExecute, etc.).
        description: Human-readable description.
    """
    _agent_registry[agent_id] = {"agent": agent, "description": description or str(type(agent).__name__)}


def get_registry() -> dict[str, Any]:
    """Return the agent registry (for use from the CLI)."""
    return _agent_registry


# ── Request/Response models ───────────────────────────────────────────────────

class RunRequest(BaseModel):
    prompt: str = ""
    context: dict[str, Any] | None = None
    response_model: str | None = None  # JSON schema name, not full model


class RunResponse(BaseModel):
    output: str = ""
    duration_s: float = 0.0
    tool_calls: int = 0
    events: list[dict] = []


class AgentInfo(BaseModel):
    id: str = ""
    description: str = ""
    tools: list[str] = []
    system_prompt: str | None = None
    agent_type: str = ""


class AgentListInfo(BaseModel):
    """Lightweight agent info for list endpoint."""
    id: str = ""
    agent_type: str = ""
    tools: list[str] = []
    description: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = __version__
    agents: int = 0


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="ChainForge API",
    description="HTTP interface for ChainForge agents",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


STATIC_DIR = Path(__file__).parent / "server_static"


def _list_agent_tools(agent) -> list[str]:
    """Extract tool names from an agent."""
    if hasattr(agent, "_all_tools"):
        return [t.spec.name for t in agent._all_tools()]
    if hasattr(agent, "tools"):
        return [t.spec.name if hasattr(t, "spec") else str(t) for t in agent.tools]
    return []


def _get_agent(agent_id: str) -> tuple[Any, dict]:
    if agent_id not in _agent_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found. Registered: {list(_agent_registry.keys())}")
    entry = _agent_registry[agent_id]
    return entry["agent"], entry


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(version=__version__, agents=len(_agent_registry))


@app.get("/api/v1/agents")
async def list_agents():
    """List all registered agents."""
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
    """Get agent information and available tools."""
    agent, entry = _get_agent(agent_id)

    tools = []
    if hasattr(agent, "_all_tools"):
        tools = [t.spec.name for t in agent._all_tools()]
    elif hasattr(agent, "tools"):
        tools = [t.spec.name if hasattr(t, "spec") else str(t) for t in agent.tools]

    system_prompt = getattr(agent, "system_prompt", None)

    return AgentInfo(
        id=agent_id,
        description=entry.get("description", ""),
        tools=tools,
        system_prompt=system_prompt,
        agent_type=type(agent).__name__,
    )


@app.post("/api/v1/eval/run")
async def run_eval(request: Request):
    """Run evaluation on a registered agent.
    Body: {"agent_id": "...", "suite_name": "...", "cases": [...]}
    """
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


@app.post("/api/v1/agents/{agent_id}/run", response_model=RunResponse)
async def run_agent(agent_id: str, request: RunRequest):
    """Run an agent and return the full result as JSON."""
    agent, _ = _get_agent(agent_id)
    start = time.monotonic()

    stream = await agent.run(request.prompt or "Hello", context=request.context)
    text_parts: list[str] = []
    all_events: list[dict] = []
    tool_call_count = 0

    async for event in stream:
        ev = {"type": event.type.value, "content": event.content, "data": event.data}
        all_events.append(ev)
        if event.type.value == "text" and event.content:
            text_parts.append(event.content)
        if event.type.value == "tool_call":
            tool_call_count += 1

    duration = time.monotonic() - start
    return RunResponse(
        output="".join(text_parts),
        duration_s=round(duration, 3),
        tool_calls=tool_call_count,
        events=all_events,
    )


@app.get("/api/v1/agents/{agent_id}/run/stream")
async def stream_agent(
    agent_id: str,
    prompt: str = Query(default="Hello", description="Prompt for the agent"),
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

        duration = time.monotonic() - start
        yield f"event: done\ndata: {json.dumps({'duration_s': round(duration, 3)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── DAG API ─────────────────────────────────────────────────────────


@app.get("/api/v1/dag/stream")
async def stream_dag(dag: str = Query(..., description="JSON-encoded DAG definition")):
    """Execute a DAG defined via query parameter and stream events."""
    try:
        dag_data = json.loads(dag)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid DAG JSON")

    from chainforge.core.graph import DAG as ChainForgeDAG, NodeType

    cf_dag = ChainForgeDAG(name=dag_data.get("name", "custom"))
    for n in dag_data.get("nodes", []):
        nt = n.get("type", "step")
        type_map = {"step": NodeType.step, "input": NodeType.input, "output": NodeType.output,
                     "router": NodeType.router, "merge": NodeType.merge}
        label = n.get("label", n.get("id", "unknown"))

        def _mk_fn(lbl, ntype):
            def fn(x=None):
                pf = f"[{ntype.upper()} {lbl}]"
                if x is not None:
                    return f"{pf} {x}"
                return pf
            return fn

        cf_dag.add_node(n["id"], fn=_mk_fn(label, nt),
                        node_type=type_map.get(nt, NodeType.step),
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


# ── Dashboard static routes ──────────────────────────────────────


@app.get("/static/{path:path}")
async def serve_static(path: str):
    """Serve static assets."""
    file_path = STATIC_DIR / path
    if not file_path.exists() or file_path.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    ext = file_path.suffix
    ct_map = {".css": "text/css", ".js": "text/javascript", ".html": "text/html",
               ".png": "image/png", ".svg": "image/svg+xml"}
    return Response(content=file_path.read_bytes(), media_type=ct_map.get(ext, "application/octet-stream"))


@app.get("/dashboard")
async def dashboard_index():
    """Dashboard main page."""
    page = STATIC_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


@app.get("/dashboard/agent-run")
async def dashboard_agent_run():
    """Agent streaming visualization page."""
    page = STATIC_DIR / "agent-run.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


@app.get("/dashboard/dag-editor")
async def dashboard_dag_editor():
    """DAG visual editor page."""
    page = STATIC_DIR / "dag-editor.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


# ── CLI entry point ───────────────────────────────────────────────────────────

def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start the ChainForge HTTP server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload on code changes.
    """
    try:
        import uvicorn
    except ImportError:
        raise ImportError("uvicorn is required. Install with: pip install 'chainforge[server]'")

    print(f"🛜  ChainForge API server v{__version__}")
    print(f"   Registered agents: {len(_agent_registry)}")
    for aid in _agent_registry:
        desc = _agent_registry[aid].get("description", "")
        print(f"     - {aid}: {desc}")
    print(f"   Listening on http://{host}:{port}")
    print(f"   Dashboard: http://{host}:{port}/dashboard")
    print(f"   API docs: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, reload=reload)
