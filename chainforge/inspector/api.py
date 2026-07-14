"""FastAPI router for the Agent Inspector API."""

from __future__ import annotations

from typing import Any

from chainforge.inspector import inspector


def get_inspector_router():
    """Create a FastAPI APIRouter with inspector endpoints.

    Usage:
        from chainforge.inspector.api import get_inspector_router
        app.include_router(get_inspector_router())
    """
    try:
        from fastapi import APIRouter, HTTPException, Query
    except ImportError:
        raise ImportError("FastAPI required. Install: pip install 'chainforge[server]'")

    router = APIRouter(prefix="/api/v1/inspector", tags=["Inspector"])
    ins = inspector

    @router.get("/agents")
    async def list_agents():
        """List all agents with inspection data."""
        return {"agents": ins.list_agents()}

    @router.get("/agents/{agent_id}")
    async def get_agent_summary(agent_id: str):
        """Get execution summary for an agent."""
        summary = ins.get_summary(agent_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return summary

    @router.get("/agents/{agent_id}/events")
    async def get_agent_events(
        agent_id: str,
        event_type: str | None = Query(None, description="Filter by event type"),
        limit: int = Query(100, ge=1, le=1000, description="Max events"),
        offset: int = Query(0, ge=0, description="Event offset"),
    ):
        """Get events for an agent with optional filtering."""
        events = ins.get_events(agent_id, event_type=event_type, limit=limit, offset=offset)
        summary = ins.get_summary(agent_id) or {}
        return {
            "agent_id": agent_id,
            "total_events": summary.get("total_events", 0),
            "returned": len(events),
            "events": [e.model_dump() for e in events],
        }

    @router.get("/agents/{agent_id}/events/stream")
    async def stream_agent_events(agent_id: str):
        """SSE stream of new events for an agent."""
        from fastapi.responses import StreamingResponse
        import json
        import asyncio

        async def event_generator():
            last_count = 0
            while True:
                events = ins.get_events(agent_id, limit=50)
                current_count = len(events)
                new_events = []
                if current_count > last_count:
                    new_events = events[:current_count - last_count]
                    last_count = current_count
                    for e in reversed(new_events):
                        yield f"data: {json.dumps(e.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                # Check summary for end_time
                summary = ins.get_summary(agent_id)
                if summary and summary.get("end_time"):
                    yield f"event: done\ndata: {json.dumps({'done': True})}\n\n"
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    return router
