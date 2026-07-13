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
import json
import time
from collections.abc import AsyncIterator
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
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
    print(f"   API docs: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, reload=reload)
