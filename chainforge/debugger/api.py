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
"""Debugger REST + WebSocket API — FastAPI router for agent debugging."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from pydantic import BaseModel

from chainforge.core.agent import Agent
from chainforge.core.stream import EventType, StreamEvent
from chainforge.debugger.session import Breakpoint, DebugSession, SessionStatus
from chainforge.logging import get_logger

logger = get_logger("debugger.api")


# ── Request/Response models ────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    name: str = "debug-session"
    agent_id: str = ""
    prompt: str = ""
    breakpoints: list[dict[str, Any]] = []


class SessionResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: float
    event_count: int = 0
    checkpoint_count: int = 0
    breakpoints: list[dict[str, Any]] = []


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class CheckpointListResponse(BaseModel):
    checkpoints: list[str]


class CheckpointStateResponse(BaseModel):
    state: dict[str, Any]


class EventListResponse(BaseModel):
    events: list[dict[str, Any]]


class BreakpointRequest(BaseModel):
    event_type: str
    condition: str | None = None


class BreakpointResponse(BaseModel):
    id: str
    event_type: str
    condition: str | None
    enabled: bool


# ── Session Store ──────────────────────────────────────────────────────────


class DebuggerAPI:
    """FastAPI-compatible router for the Agent Visual Debugger.

    Usage (in server.py):
        debugger_api = DebuggerAPI()
        app.include_router(debugger_api.router, prefix="/api/v1/debug")
    """

    def __init__(self):
        self._sessions: dict[str, DebugSession] = {}
        self._ws_clients: dict[str, list] = {}  # session_id -> [ws_send_callbacks]
        self._agent_registry: dict[str, Agent] = {}

        # Import lazily to avoid FastAPI dependency at import time
        from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
        from fastapi.responses import JSONResponse

        self.router = APIRouter()

        # ── Register routes ─────────────────────────────────────────────

        @self.router.get("/sessions", response_model=SessionListResponse)
        async def list_sessions():
            sessions = [self._session_to_response(s) for s in self._sessions.values()]
            return SessionListResponse(sessions=sessions)

        @self.router.post("/sessions", response_model=SessionResponse, status_code=201)
        async def create_session(req: CreateSessionRequest):
            agent = self._agent_registry.get(req.agent_id)
            if agent is None and req.agent_id:
                raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")
            session = DebugSession(
                name=req.name or f"debug-{req.agent_id}",
                agent=agent,
                metadata={"agent_id": req.agent_id, "prompt": req.prompt},
            )
            for bp_data in req.breakpoints:
                session.add_breakpoint(Breakpoint(**bp_data))
            self._sessions[session.id] = session
            self._ws_clients[session.id] = []
            return self._session_to_response(session)

        @self.router.get("/sessions/{session_id}", response_model=SessionResponse)
        async def get_session(session_id: str):
            session = self._get_session(session_id)
            return self._session_to_response(session)

        @self.router.delete("/sessions/{session_id}")
        async def delete_session(session_id: str):
            self._sessions.pop(session_id, None)
            self._ws_clients.pop(session_id, None)
            return JSONResponse({"status": "deleted"})

        # ── Execution control ──────────────────────────────────────────

        @self.router.post("/sessions/{session_id}/run")
        async def run_session(session_id: str):
            session = self._get_session(session_id)
            prompt = session.metadata.get("prompt", "")
            if not prompt:
                raise HTTPException(status_code=400, detail="No prompt set")
            if session.agent is None:
                # Run in observation-only mode (just collect events)
                raise HTTPException(status_code=400, detail="No agent bound")

            # Start execution in background
            asyncio.create_task(self._execute_session(session, prompt))
            return JSONResponse({"status": "started", "session_id": session_id})

        @self.router.post("/sessions/{session_id}/pause")
        async def pause_session(session_id: str):
            session = self._get_session(session_id)
            session.pause()
            return JSONResponse({"status": "pausing"})

        @self.router.post("/sessions/{session_id}/resume")
        async def resume_session(session_id: str):
            session = self._get_session(session_id)
            session.resume()
            return JSONResponse({"status": "resumed"})

        @self.router.post("/sessions/{session_id}/step")
        async def step_session(session_id: str):
            session = self._get_session(session_id)
            session.step()
            return JSONResponse({"status": "stepping"})

        # ── Checkpoints ────────────────────────────────────────────────

        @self.router.get("/sessions/{session_id}/checkpoints", response_model=CheckpointListResponse)
        async def list_checkpoints(session_id: str):
            session = self._get_session(session_id)
            return CheckpointListResponse(checkpoints=session.list_checkpoints())

        @self.router.get("/sessions/{session_id}/checkpoints/{checkpoint_id}", response_model=CheckpointStateResponse)
        async def get_checkpoint(session_id: str, checkpoint_id: str):
            session = self._get_session(session_id)
            state = session.get_checkpoint_state(checkpoint_id)
            if state is None:
                raise HTTPException(status_code=404, detail="Checkpoint not found")
            return CheckpointStateResponse(state=state)

        # ── Events ─────────────────────────────────────────────────────

        @self.router.get("/sessions/{session_id}/events", response_model=EventListResponse)
        async def list_events(session_id: str, limit: int = 200):
            session = self._get_session(session_id)
            events = session.events[-limit:]
            return EventListResponse(events=[self._event_to_dict(e) for e in events])

        # ── Breakpoints ────────────────────────────────────────────────

        @self.router.post("/sessions/{session_id}/breakpoints", response_model=BreakpointResponse)
        async def add_breakpoint(session_id: str, req: BreakpointRequest):
            session = self._get_session(session_id)
            bp = session.add_breakpoint(Breakpoint(event_type=req.event_type, condition=req.condition))
            return BreakpointResponse(id=bp.id, event_type=bp.event_type, condition=bp.condition, enabled=bp.enabled)

        @self.router.delete("/sessions/{session_id}/breakpoints/{bp_id}")
        async def remove_breakpoint(session_id: str, bp_id: str):
            session = self._get_session(session_id)
            session.remove_breakpoint(bp_id)
            return JSONResponse({"status": "deleted"})

        # ── Provenance ─────────────────────────────────────────────────

        @self.router.get("/sessions/{session_id}/provenance")
        async def get_provenance(session_id: str):
            session = self._get_session(session_id)
            return session.provenance_graph()

        # ── WebSocket ──────────────────────────────────────────────────

        @self.router.websocket("/sessions/{session_id}/ws")
        async def session_websocket(websocket: WebSocket, session_id: str):
            await websocket.accept()
            session = self._get_session(session_id)
            ws_key = f"{session_id}_{id(websocket)}"

            # Register this WS client
            async def ws_callback(event: StreamEvent):
                try:
                    await websocket.send_json(self._event_to_dict(event))
                except Exception:
                    pass

            self._ws_clients[session_id].append(ws_callback)

            try:
                # Send current state
                await websocket.send_json({"type": "connected", "session_id": session_id})

                # Listen for incoming commands
                while True:
                    data = await websocket.receive_text()
                    try:
                        msg = json.loads(data)
                        await self._handle_ws_command(session, msg, websocket)
                    except json.JSONDecodeError:
                        await websocket.send_json({"type": "error", "message": "Invalid JSON"})
            except WebSocketDisconnect:
                pass
            finally:
                try:
                    self._ws_clients[session_id].remove(ws_callback)
                except ValueError:
                    pass

    # ── Internal helpers ────────────────────────────────────────────────

    def register_agent(self, agent_id: str, agent: Agent) -> None:
        """Register an agent for debugging by ID."""
        self._agent_registry[agent_id] = agent

    def _get_session(self, session_id: str) -> DebugSession:
        if session_id not in self._sessions:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        return self._sessions[session_id]

    async def _execute_session(self, session: DebugSession, prompt: str) -> None:
        """Run the agent in background, broadcasting events to WS clients."""
        async def broadcast(event: StreamEvent) -> None:
            event_dict = self._event_to_dict(event)
            for cb in list(self._ws_clients.get(session.id, [])):
                try:
                    await cb(event)
                except Exception:
                    pass

        async for event in session.run(prompt, event_callback=broadcast):
            # Also broadcast during step/pause
            if event.type == EventType.done:
                for cb in list(self._ws_clients.get(session.id, [])):
                    try:
                        await cb({"type": "done", "content": event.content})
                    except Exception:
                        pass

    async def _handle_ws_command(self, session: DebugSession,
                                  msg: dict, ws: Any) -> None:
        cmd = msg.get("command", "")
        if cmd == "pause":
            session.pause()
            await ws.send_json({"type": "paused"})
        elif cmd == "resume":
            session.resume()
            await ws.send_json({"type": "resumed"})
        elif cmd == "step":
            session.step()
            await ws.send_json({"type": "stepping"})
        elif cmd == "get_state":
            state = session.get_checkpoint_state(msg.get("checkpoint_id", ""))
            await ws.send_json({"type": "state", "data": state or {}})
        elif cmd == "list_checkpoints":
            checkpoints = session.list_checkpoints()
            await ws.send_json({"type": "checkpoints", "data": checkpoints})
        else:
            await ws.send_json({"type": "error", "message": f"Unknown command: {cmd}"})

    @staticmethod
    def _session_to_response(session: DebugSession) -> SessionResponse:
        return SessionResponse(
            id=session.id,
            name=session.name,
            status=session.status.value,
            created_at=session.created_at,
            event_count=len(session.events),
            checkpoint_count=len(session.list_checkpoints()),
            breakpoints=[bp.model_dump() for bp in session.breakpoints],
        )

    @staticmethod
    def _event_to_dict(event: StreamEvent) -> dict[str, Any]:
        return {
            "type": event.type.value,
            "content": event.content,
            "data": event.data,
            "timestamp": time.time(),
        }
