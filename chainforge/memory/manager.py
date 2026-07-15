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
"""Memory manager — coordinates multiple memory types for an Agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

import logging
from chainforge.logging import get_logger, log_data
from chainforge.memory.buffer import BufferMemory
from chainforge.memory.vector import VectorMemory
from chainforge.memory.utils import summarize_messages, trim_messages

logger = get_logger("memory.manager")


class MemoryManager(BaseModel):
    """Coordinates working, episodic, and semantic memory for an Agent.

    The manager provides a unified interface for storing and retrieving
    across all memory levels:

      - working (BufferMemory):    Recent context, full fidelity, sliding window
      - episodic (VectorMemory):   Past sessions, semantic retrieval
      - semantic (VectorMemory):   Knowledge, facts, user preferences

    Usage:
        manager = MemoryManager(
            working=BufferMemory(max_messages=20),
            episodic=VectorMemory(),
            semantic=VectorMemory(),
        )
        await manager.store("User likes Python", {"type": "preference"})
        context = await manager.get_context("What does the user like?")
    """

    working: BufferMemory = Field(default_factory=lambda: BufferMemory(max_messages=20))
    episodic: VectorMemory | None = Field(default=None, description="Past session memory")
    semantic: VectorMemory | None = Field(default=None, description="Knowledge / preferences")
    auto_summarize: bool = Field(default=True, description="Auto-summarize when storing")
    llm: Any = Field(default=None, description="LLM for summarization (required if auto_summarize=True)")

    model_config = {"arbitrary_types_allowed": True}

    async def store(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        memory_level: str = "auto",
    ) -> None:
        """Store text across the appropriate memory levels.

        Args:
            text: Text content to store.
            metadata: Optional metadata (role, session, type, etc.).
            memory_level: "working", "episodic", "semantic", or "auto".
        """
        # Always store in working memory
        from chainforge.core.message import Message as CfMessage
        role = (metadata or {}).get("role", "user") or "user"
        self.working.messages.append(CfMessage(role=role, content=text))
        if len(self.working.messages) > self.working.max_messages:
            if self.auto_summarize and self.llm is not None:
                # Auto-summarize old messages
                self.working.messages = await summarize_messages(
                    self.working.messages,
                    self.llm,
                    max_messages=self.working.max_messages // 2,
                )
            else:
                self.working.messages = self.working.messages[-self.working.max_messages:]

        # Store in episodic memory
        if self.episodic and (memory_level in ("auto", "episodic")):
            await self.episodic.add(text, metadata={"level": "episodic", **(metadata or {})})

        # Store in semantic memory if it's a knowledge/preference statement
        if self.semantic and (memory_level == "semantic" or self._is_knowledge(text)):
            await self.semantic.add(text, metadata={"level": "semantic", **(metadata or {})})

    async def get_context(self, query: str, k: int = 5) -> str:
        """Build a context string from all memory levels relevant to *query*.

        Args:
            query: The current prompt or question.
            k: Max results per memory level.

        Returns:
            A formatted context string.
        """
        parts = []

        # Working memory (recent conversation)
        recent = self.working.get_history()
        if recent:
            texts = []
            for m in recent:
                if m.content:
                    texts.append(f"[{m.role.value}] {m.content[:200]}")
            parts.append(f"[Recent Conversation]\n" + "\n".join(texts[-10:]))

        # Episodic memory (semantically related past sessions)
        if self.episodic:
            episodic_results = await self.episodic.query(query, k=k, min_score=0.3)
            if episodic_results:
                entries = "\n".join(
                    f"  - [{r['timestamp'][:10]}] {r['text'][:200]}" for r in episodic_results
                )
                parts.append(f"[Related Past Sessions]\n{entries}")

        # Semantic memory (knowledge / preferences)
        if self.semantic:
            semantic_results = await self.semantic.query(query, k=k, min_score=0.4)
            if semantic_results:
                entries = "\n".join(f"  - {r['text'][:200]}" for r in semantic_results)
                parts.append(f"[Known Facts]\n{entries}")

        return "\n\n".join(parts)

    async def remember(self, text: str) -> None:
        """Store a fact or preference in semantic memory."""
        await self.store(text, {"type": "preference", "role": "system"}, memory_level="semantic")

    async def clear(self) -> None:
        """Clear all memory levels."""
        self.working.clear()
        if self.episodic:
            await self.episodic.clear()
        if self.semantic:
            await self.semantic.clear()
        log_data(logger, logging.INFO, "All memory levels cleared")

    def stats(self) -> dict[str, Any]:
        """Return memory usage statistics."""
        stats: dict[str, Any] = {
            "working": len(getattr(self.working, 'messages', [])),
        }
        if self.episodic:
            stats["episodic"] = self.episodic.stats()
        if self.semantic:
            stats["semantic"] = self.semantic.stats()
        return stats

    @staticmethod
    def _is_knowledge(text: str) -> bool:
        """Heuristic: does the text look like a knowledge statement?"""
        knowledge_prefixes = [
            "the user ", "user is ", "user likes ", "user prefers ",
            "i am ", "my name ", "i like ", "i prefer ",
            "remember ", "fact: ", "note: ",
        ]
        lower = text.lower().strip()
        return any(lower.startswith(p) for p in knowledge_prefixes)
