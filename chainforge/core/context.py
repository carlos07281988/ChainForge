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
"""InvocationContext — standardized context for agent execution.

Inspired by Google ADK's InvocationContext and MS Agent Framework's
AgentClient context. Provides a uniform container for session metadata,
user identity, tracing, and configuration across the entire agent
execution pipeline.

Usage:
    ctx = InvocationContext(
        session_id="session-123",
        user_id="user-456",
        metadata={"source": "web"},
    )
    stream = await agent.run("Hello", context=ctx.to_dict())
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class InvocationContext(BaseModel):
    """Standardized context for agent invocation.

    Passed through the entire agent execution pipeline (middleware,
    callbacks, tools, hooks) to carry session metadata, identity,
    tracing information, and user-provided configuration.
    """

    session_id: str = Field(
        default_factory=lambda: f"sess_{uuid.uuid4().hex[:12]}",
        description="Unique conversation/session identifier",
    )
    thread_id: str | None = Field(
        default=None,
        description="Thread identifier for state checkpointing",
    )
    user_id: str | None = Field(
        default=None,
        description="End-user identifier for authentication/audit",
    )
    invocation_id: str = Field(
        default_factory=lambda: f"inv_{uuid.uuid4().hex[:12]}",
        description="Unique invocation identifier (one call to agent.run())",
    )
    trace_id: str | None = Field(
        default=None,
        description="Distributed tracing correlation ID",
    )
    locale: str = Field(
        default="en-US",
        description="Locale for content generation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary user-defined context data",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for routing, filtering, and analytics",
    )
    created_at: float = Field(
        default_factory=time.time,
        description="Context creation timestamp",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for passing as Agent context."""
        return {
            "_invocation_context": self,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "invocation_id": self.invocation_id,
            "thread_id": self.thread_id,
            "trace_id": self.trace_id,
            "locale": self.locale,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvocationContext":
        """Reconstruct from a plain dict (extracted from Agent context)."""
        ic = data.get("_invocation_context")
        if isinstance(ic, cls):
            return ic
        return cls(
            session_id=data.get("session_id", cls.model_fields["session_id"].default),
            thread_id=data.get("thread_id"),
            user_id=data.get("user_id"),
            invocation_id=data.get("invocation_id", cls.model_fields["invocation_id"].default),
            trace_id=data.get("trace_id"),
            locale=data.get("locale", "en-US"),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )


def get_invocation_context(ctx: dict[str, Any] | None) -> InvocationContext:
    """Extract InvocationContext from Agent context dict, creating one if absent."""
    if ctx is None:
        return InvocationContext()
    ic = ctx.get("_invocation_context")
    if isinstance(ic, InvocationContext):
        return ic
    return InvocationContext.from_dict(ctx)


def with_context(session_id: str | None = None,
                 user_id: str | None = None,
                 thread_id: str | None = None,
                 tags: list[str] | None = None,
                 **metadata: Any) -> dict[str, Any]:
    """Quick helper to build an Agent context dict with InvocationContext.

    Usage:
        ctx = with_context(session_id="abc", user_id="user-1", source="web")
        stream = await agent.run("Hello", context=ctx)
    """
    ic = InvocationContext(
        session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        thread_id=thread_id,
        tags=tags or [],
        metadata=metadata,
    )
    return ic.to_dict()
