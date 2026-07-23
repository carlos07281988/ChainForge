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
"""Thread/Session Manager — conversation thread management for agents.

Inspired by MS Agent Framework's ConversationId/TurnId system and Google ADK's
session management. Provides thread creation, turn tracking, history persistence,
and metadata management for multi-turn conversations.

Usage:
    mgr = ThreadManager()
    thread = await mgr.create_thread(user_id="user-1")
    msg = await mgr.add_message(thread.id, Message.user("Hello"))
    history = await mgr.get_history(thread.id)
    threads = await mgr.list_threads(user_id="user-1")
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.message import Message


class ThreadMetadata(BaseModel):
    """Metadata for a conversation thread."""

    title: str = Field(default="", description="Conversation title")
    user_id: str | None = Field(default=None, description="End-user identifier")
    agent_id: str | None = Field(default=None, description="Agent identifier")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    custom: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")


class TurnInfo(BaseModel):
    """Information about a single turn in a thread."""

    turn_id: str = Field(description="Unique turn identifier")
    timestamp: float = Field(default_factory=time.time)
    message_count: int = Field(default=0, description="Messages in this turn")
    tool_call_count: int = Field(default=0)
    duration_ms: float | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreadInfo(BaseModel):
    """Information about a conversation thread."""

    id: str = Field(default_factory=lambda: f"thread_{uuid.uuid4().hex[:12]}")
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    message_count: int = Field(default=0)
    turn_count: int = Field(default=0)
    metadata: ThreadMetadata = Field(default_factory=ThreadMetadata)
    is_active: bool = Field(default=True)


class ThreadManager(BaseModel):
    """Manage conversation threads with history, metadata, and turn tracking.

    Provides thread-level isolation for multi-turn conversations with
    message history persistence, turn tracking, and metadata management.

    Usage:
        mgr = ThreadManager()
        thread = await mgr.create_thread(user_id="user-1")
        await mgr.add_message(thread.id, Message.user("Hello"))
        history = await mgr.get_history(thread.id)
    """

    name: str = Field(default="default")
    max_messages_per_thread: int = Field(default=500)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._threads: dict[str, ThreadInfo] = {}
        self._messages: dict[str, list[Message]] = {}
        self._turns: dict[str, list[TurnInfo]] = {}

    # ── Thread CRUD ────────────────────────────────────────────────────

    async def create_thread(self, user_id: str | None = None,
                            title: str = "",
                            tags: list[str] | None = None,
                            agent_id: str | None = None,
                            custom: dict[str, Any] | None = None) -> ThreadInfo:
        """Create a new conversation thread."""
        thread = ThreadInfo(
            metadata=ThreadMetadata(
                title=title, user_id=user_id, agent_id=agent_id,
                tags=tags or [], custom=custom or {},
            ),
        )
        self._threads[thread.id] = thread
        self._messages[thread.id] = []
        self._turns[thread.id] = []
        return thread

    async def get_thread(self, thread_id: str) -> ThreadInfo | None:
        return self._threads.get(thread_id)

    async def delete_thread(self, thread_id: str) -> bool:
        if thread_id not in self._threads:
            return False
        del self._threads[thread_id]
        self._messages.pop(thread_id, None)
        self._turns.pop(thread_id, None)
        return True

    async def update_thread_metadata(self, thread_id: str,
                                      **kw: Any) -> ThreadInfo | None:
        thread = self._threads.get(thread_id)
        if thread is None:
            return None
        if "title" in kw:
            thread.metadata.title = kw["title"]
        if "tags" in kw:
            thread.metadata.tags = kw["tags"]
        if "custom" in kw:
            thread.metadata.custom.update(kw["custom"])
        if "user_id" in kw:
            thread.metadata.user_id = kw["user_id"]
        if "agent_id" in kw:
            thread.metadata.agent_id = kw["agent_id"]
        thread.updated_at = time.time()
        return thread

    async def list_threads(self, user_id: str | None = None,
                           agent_id: str | None = None,
                           active_only: bool = True,
                           limit: int = 50) -> list[ThreadInfo]:
        results: list[ThreadInfo] = []
        for thread in sorted(self._threads.values(),
                             key=lambda t: t.updated_at, reverse=True):
            if active_only and not thread.is_active:
                continue
            if user_id and thread.metadata.user_id != user_id:
                continue
            if agent_id and thread.metadata.agent_id != agent_id:
                continue
            results.append(thread)
            if len(results) >= limit:
                break
        return results

    # ── Message management ─────────────────────────────────────────────

    async def add_message(self, thread_id: str, message: Message) -> int:
        """Add a message to a thread. Returns the message index."""
        if thread_id not in self._messages:
            raise ValueError(f"Thread not found: {thread_id}")
        msgs = self._messages[thread_id]
        msgs.append(message)
        thread = self._threads[thread_id]
        thread.message_count = len(msgs)
        thread.updated_at = time.time()

        # Prune if over limit
        if len(msgs) > self.max_messages_per_thread:
            overflow = len(msgs) - self.max_messages_per_thread
            self._messages[thread_id] = msgs[overflow:]

        return len(self._messages[thread_id]) - 1

    async def add_messages(self, thread_id: str,
                           messages: list[Message]) -> list[int]:
        indices = []
        for msg in messages:
            idx = await self.add_message(thread_id, msg)
            indices.append(idx)
        return indices

    async def get_history(self, thread_id: str, *,
                           limit: int | None = None,
                           offset: int = 0) -> list[Message]:
        msgs = self._messages.get(thread_id, [])
        if offset > 0:
            msgs = msgs[offset:]
        if limit is not None:
            msgs = msgs[:limit]
        return list(msgs)

    async def get_last_n(self, thread_id: str, n: int = 10) -> list[Message]:
        msgs = self._messages.get(thread_id, [])
        return list(msgs[-n:])

    async def clear_history(self, thread_id: str) -> bool:
        if thread_id not in self._messages:
            return False
        self._messages[thread_id] = []
        thread = self._threads.get(thread_id)
        if thread:
            thread.message_count = 0
            thread.updated_at = time.time()
        return True

    # ── Turn tracking ──────────────────────────────────────────────────

    async def start_turn(self, thread_id: str,
                          metadata: dict[str, Any] | None = None) -> TurnInfo:
        turn = TurnInfo(
            turn_id=f"turn_{uuid.uuid4().hex[:8]}",
            metadata=metadata or {},
        )
        if thread_id in self._turns:
            self._turns[thread_id].append(turn)
        thread = self._threads.get(thread_id)
        if thread:
            thread.turn_count = len(self._turns.get(thread_id, []))
            thread.updated_at = time.time()
        return turn

    async def end_turn(self, thread_id: str, turn_id: str,
                        duration_ms: float | None = None) -> None:
        turns = self._turns.get(thread_id, [])
        for turn in turns:
            if turn.turn_id == turn_id:
                turn.duration_ms = duration_ms
                break

    async def get_turns(self, thread_id: str, limit: int = 20) -> list[TurnInfo]:
        turns = self._turns.get(thread_id, [])
        return list(reversed(turns))[:limit]

    # ── Stats ──────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        total_messages = sum(len(msgs) for msgs in self._messages.values())
        active_threads = sum(1 for t in self._threads.values() if t.is_active)
        return {
            "name": self.name,
            "total_threads": len(self._threads),
            "active_threads": active_threads,
            "total_messages": total_messages,
            "avg_messages_per_thread": (
                total_messages / len(self._threads)
                if self._threads else 0
            ),
        }
