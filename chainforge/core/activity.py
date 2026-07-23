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
"""Structured Activity Logging — queryable, categorized activity logs.

Inspired by Google ADK's activity logging system. Activities are structured
log entries with categories, levels, and structured payloads. They can be
queried, filtered, and exported for monitoring and debugging.

Usage:
    logger = ActivityLogger()
    logger.info("agent.run", "Agent started", session_id="sess-1")
    logger.tool_call("get_weather", {"city": "Beijing"}, duration_ms=120)
    logger.error("tool.error", "Tool failed", error="Timeout")
    events = logger.query(category="tool.*", limit=10)
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActivityLevel(str, Enum):
    """Severity/level of an activity event."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActivityEvent(BaseModel):
    """A single structured activity event."""

    id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    timestamp: float = Field(default_factory=time.time)
    level: ActivityLevel = Field(default=ActivityLevel.INFO)
    category: str = Field(description="Dot-notation category (e.g. 'tool.search', 'agent.run')")
    message: str = Field(description="Human-readable summary")
    session_id: str | None = Field(default=None)
    invocation_id: str | None = Field(default=None)
    tool_name: str | None = Field(default=None)
    duration_ms: float | None = Field(default=None)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)

    @property
    def datetime(self) -> str:
        return datetime.fromtimestamp(self.timestamp).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude={"id"}, exclude_none=True)

    def __repr__(self) -> str:
        return (f"[{self.level.value.upper()}] {self.category}: "
                f"{self.message[:80]}")


class ActivityLogger(BaseModel):
    """Structured activity logger with querying and filtering.

    Provides categorized, queryable activity logging for agent execution.
    Useful for monitoring, debugging, and compliance auditing.

    Usage:
        log = ActivityLogger(max_events=1000)
        log.info("agent.run", "Processing request", session_id="sess-1")
        log.tool_call("get_weather", {"city": "Beijing"}, duration_ms=120)
        log.error("tool.error", "Failed", error="Timeout")

        for event in log.query(category="tool.*", level="error"):
            print(event)
    """

    name: str = Field(default="default")
    max_events: int = Field(default=10000)
    _events: list[ActivityEvent] = []

    def info(self, category: str, message: str, *,
             session_id: str | None = None,
             invocation_id: str | None = None,
             tool_name: str | None = None,
             duration_ms: float | None = None,
             payload: dict[str, Any] | None = None,
             tags: list[str] | None = None) -> ActivityEvent:
        return self._log(ActivityLevel.INFO, category, message,
                         session_id=session_id, invocation_id=invocation_id,
                         tool_name=tool_name, duration_ms=duration_ms,
                         payload=payload, tags=tags)

    def warning(self, category: str, message: str, *,
                session_id: str | None = None, **kw: Any) -> ActivityEvent:
        return self._log(ActivityLevel.WARNING, category, message,
                         session_id=session_id, **kw)

    def error(self, category: str, message: str, *,
              error: str | None = None,
              session_id: str | None = None, **kw: Any) -> ActivityEvent:
        return self._log(ActivityLevel.ERROR, category, message,
                         session_id=session_id, error=error, **kw)

    def debug(self, category: str, message: str, *,
              session_id: str | None = None, **kw: Any) -> ActivityEvent:
        return self._log(ActivityLevel.DEBUG, category, message,
                         session_id=session_id, **kw)

    def tool_call(self, tool_name: str, args: dict[str, Any], *,
                  duration_ms: float | None = None,
                  session_id: str | None = None,
                  **kw: Any) -> ActivityEvent:
        return self._log(
            ActivityLevel.INFO, f"tool.{tool_name}",
            f"Tool call: {tool_name}",
            tool_name=tool_name, duration_ms=duration_ms,
            session_id=session_id, payload={"args": args}, **kw,
        )

    def tool_result(self, tool_name: str, result: Any, *,
                    duration_ms: float | None = None,
                    session_id: str | None = None,
                    **kw: Any) -> ActivityEvent:
        result_str = str(result)[:200]
        return self._log(
            ActivityLevel.INFO, f"tool.{tool_name}.result",
            f"Tool result: {tool_name} -> {result_str}",
            tool_name=tool_name, duration_ms=duration_ms,
            session_id=session_id, payload={"result_preview": result_str}, **kw,
        )

    def _log(self, level: ActivityLevel, category: str, message: str, *,
             session_id: str | None = None,
             invocation_id: str | None = None,
             tool_name: str | None = None,
             duration_ms: float | None = None,
             payload: dict[str, Any] | None = None,
             error: str | None = None,
             tags: list[str] | None = None) -> ActivityEvent:
        event = ActivityEvent(
            level=level, category=category, message=message,
            session_id=session_id, invocation_id=invocation_id,
            tool_name=tool_name, duration_ms=duration_ms,
            payload=payload or {}, error=error, tags=tags or [],
        )
        self._events.append(event)
        if len(self._events) > self.max_events:
            self._events.pop(0)
        return event

    def query(self, *, category: str | None = None,
              level: ActivityLevel | str | None = None,
              session_id: str | None = None,
              tool_name: str | None = None,
              tag: str | None = None,
              since: float | None = None,
              until: float | None = None,
              limit: int = 50) -> list[ActivityEvent]:
        """Query activity events with filters.

        Args:
            category: Filter by category (supports glob '*', e.g. 'tool.*').
            level: Filter by minimum level.
            session_id: Filter by session.
            tool_name: Filter by tool name.
            tag: Filter by tag.
            since: Only events after this timestamp.
            until: Only events before this timestamp.
            limit: Max results.

        Returns:
            Matching events, most recent first.
        """
        results: list[ActivityEvent] = []
        import fnmatch
        for event in reversed(self._events):
            if category and not fnmatch.fnmatch(event.category, category):
                continue
            if level:
                lvl = level if isinstance(level, ActivityLevel) else ActivityLevel(level)
                if ActivityLevel._member_map_[event.level.name].value != lvl.value:
                    min_order = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
                    if min_order.get(event.level.value, 0) < min_order.get(lvl.value, 0):
                        continue
            if session_id and event.session_id != session_id:
                continue
            if tool_name and event.tool_name != tool_name:
                continue
            if tag and tag not in event.tags:
                continue
            if since is not None and event.timestamp < since:
                continue
            if until is not None and event.timestamp > until:
                continue
            results.append(event)
            if len(results) >= limit:
                break
        return results

    def stats(self) -> dict[str, Any]:
        """Get aggregate statistics about logged activities."""
        counts: dict[str, int] = {}
        level_counts: dict[str, int] = {}
        tool_counts: dict[str, int] = {}
        for e in self._events:
            cat = e.category.split(".")[0] if "." in e.category else e.category
            counts[cat] = counts.get(cat, 0) + 1
            level_counts[e.level.value] = level_counts.get(e.level.value, 0) + 1
            if e.tool_name:
                tool_counts[e.tool_name] = tool_counts.get(e.tool_name, 0) + 1
        return {
            "name": self.name,
            "total_events": len(self._events),
            "by_category": counts,
            "by_level": level_counts,
            "by_tool": tool_counts,
        }

    def clear(self) -> None:
        self._events.clear()

    def export_json(self, path: str, *, pretty: bool = False) -> None:
        """Export all events to a JSON file."""
        import json as _json
        data = [e.model_dump() for e in self._events]
        with open(path, "w") as f:
            _json.dump(data, f, indent=2 if pretty else None)

    @property
    def count(self) -> int:
        return len(self._events)
