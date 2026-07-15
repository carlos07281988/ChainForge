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
"""AutoMemory Manager — MemGPT-style automatic memory management.

Extends MemoryManager with:
  - Automatic archival: moves old/unused context to long-term storage
  - Retrieval-triggered recall: auto-queries memory when relevant context appears
  - Conflict resolution: detects and resolves contradictory stored facts
  - Forgetting curve: deprioritizes old/unused memories based on recency and frequency

Usage:
    from chainforge.memory import AutoMemoryManager

    memory = AutoMemoryManager(llm=llm)
    await memory.store("User likes Python", {"type": "preference"})
    context = await memory.recall("What language does the user like?")
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from chainforge.core.message import Message
from chainforge.logging import get_logger
from chainforge.memory.manager import MemoryManager
from chainforge.memory.vector import VectorMemory
from chainforge.memory.buffer import BufferMemory
from chainforge.memory.utils import summarize_messages

logger = get_logger("memory.auto_memory")

CONFLICT_PROMPT = """The following two stored facts appear to conflict:

Fact A: {fact_a}
Fact B: {fact_b}

Which one is more likely correct? Consider recency, specificity, and context.
Respond with: "A" if Fact A is correct, "B" if Fact B is correct,
or "BOTH" if they can both be true in different contexts."""


class AutoMemoryManager:
    """MemGPT-style automatic memory manager.

    Extends MemoryManager with:
      - Auto-archival: when working memory exceeds threshold, summarize and archive
      - Recall: triggered by semantic similarity to current context
      - Conflict resolution: detects contradictory facts and prompts LLM to resolve
      - Recency weighting: newer facts are preferred in get_context()

    Usage:
        memory = AutoMemoryManager(llm=my_llm, archive_threshold=30)
        await memory.store("User likes Python")
        context = await memory.recall("What does the user like?")
    """

    def __init__(
        self,
        llm=None,
        working_max: int = 30,
        archive_threshold: int = 25,
        recall_k: int = 5,
        enable_conflict_detection: bool = True,
        enable_forgetting: bool = True,
    ):
        self._memory = MemoryManager(
            working=BufferMemory(max_messages=working_max),
            episodic=VectorMemory(),
            semantic=VectorMemory(),
            auto_summarize=True,
            llm=llm,
        )
        self._working = self._memory.working
        self._episodic = self._memory.episodic
        self._semantic = self._memory.semantic
        self._memory.auto_summarize = self._memory.auto_summarize
        self._llm = self._memory.llm
        self.archive_threshold = archive_threshold
        self.recall_k = recall_k
        self.enable_conflict_detection = enable_conflict_detection
        self.enable_forgetting = enable_forgetting
        self._access_log: dict[str, list[float]] = {}  # fact_key -> [timestamps]

    async def store(self, text: str, metadata: dict[str, Any] | None = None, *, memory_level: str = "auto") -> None:
        """Store text with automatic archival if needed."""
        await super().store(text, metadata=metadata, memory_level=memory_level)

        # Check for archival trigger
        if self._memory.auto_summarize and self._llm and len(self._working.messages) > self.archive_threshold:
            await self._auto_archive()

        # Conflict detection
        if self.enable_conflict_detection and self._semantic and self._llm:
            await self._check_conflicts(text)

        # Log access
        if self.enable_forgetting:
            key = text[:50]
            if key not in self._access_log:
                self._access_log[key] = []
            self._access_log[key].append(time.time())

    async def recall(self, query: str, k: int | None = None) -> str:
        """Retrieve context with recency-weighted scoring.

        Unlike get_context() which is flat, recall() applies:
        - Recency boost: recently accessed facts rank higher
        - Relevance threshold: only include highly relevant facts
        - Deduplication: similar facts are merged

        Args:
            query: The current context / question.
            k: Max results (defaults to self.recall_k).

        Returns:
            Formatted context string with recency-weighted results.
        """
        k = k or self.recall_k
        base_context = await self.get_context(query, k=k + 3)

        # Apply forgetting curve: deprioritize old/unused facts
        if self.enable_forgetting and self._semantic:
            results = await self._semantic.query(query, k=k + 5, min_score=0.2)
            weighted = []
            now = time.time()
            for r in results:
                key = r["text"][:50]
                accesses = self._access_log.get(key, [])
                if accesses:
                    # Recency score: 0 (never) to 1 (just now)
                    last_access = max(accesses)
                    recency = 1.0 / (1.0 + (now - last_access) / 3600)  # decay over hours
                else:
                    recency = 0.3  # default for un-tracked
                weighted.append((r["score"] * 0.7 + recency * 0.3, r))

            weighted.sort(key=lambda x: x[0], reverse=True)
            top = weighted[:k]

            if top:
                entries = []
                for score, r in top:
                    ts = r.get("timestamp", "")[:10] if r.get("timestamp") else ""
                    entries.append(f"  - [{ts}] (score={score:.2f}) {r['text'][:200]}")
                context = "\n".join(entries)
                return f"[Recency-Weighted Memory]\n{context}"

        return base_context

    async def _auto_archive(self) -> None:
        """Summarize older working memory messages and archive to episodic memory."""
        if not self._llm:
            return

        archive_chunk = self._working.messages[:-self.archive_threshold // 2]
        if len(archive_chunk) < 5:
            return

        logger.info(f"Auto-archiving {len(archive_chunk)} messages")

        # Summarize
        archive_text = "\n".join(
            f"[{m.role.value}] {m.content or ''}" for m in archive_chunk if m.content
        )

        try:
            resp = await self._llm.generate([
                Message.system("Summarize the key information in this conversation for long-term memory:"),
                Message.user(archive_text),
            ])
            summary = resp.content or ""
            if summary and self._semantic:
                await self._semantic.add(summary, metadata={"type": "archive", "archived_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
                logger.info(f"Archived summary ({len(summary)} chars)")

            # Keep only recent messages
            self._working.messages = self._working.messages[-self.archive_threshold // 2:]

        except Exception as e:
            logger.warning(f"Auto-archive failed: {e}")

    async def _check_conflicts(self, text: str) -> None:
        """Detect and resolve conflicting facts in semantic memory."""
        if not self._semantic or not self._llm:
            return

        # Find similar existing facts
        similar = await self._semantic.query(text, k=3, min_score=0.6)
        for entry in similar:
            existing = entry["text"]
            if existing == text:
                continue

            # Check for contradiction
            conflict_prompt = CONFLICT_PROMPT.format(fact_a=existing, fact_b=text)
            resp = await self._llm.generate([Message.user(conflict_prompt)])
            decision = (resp.content or "").strip().upper()

            if decision.startswith("B"):
                # Keep existing, new fact contradicts
                logger.debug(f"Conflict resolved: keeping '{existing[:30]}', rejecting '{text[:30]}'")
                # Remove the new (contradictory) fact
                await self._semantic.remove(entry["id"] if "id" in entry else "")
            elif decision.startswith("A"):
                # Existing is correct, new is wrong
                logger.debug(f"Conflict resolved: existing '{existing[:30]}' is correct")
            else:
                # Both can coexist
                pass

    def stats(self) -> dict[str, Any]:
        """Extended stats including access log size."""
        base = super().stats()
        base["access_log_entries"] = len(self._access_log)
        base["auto_memory"] = {
            "archive_threshold": self.archive_threshold,
            "conflict_detection": self.enable_conflict_detection,
            "forgetting_curve": self.enable_forgetting,
        }
        return base

    async def clear(self) -> None:
        """Clear all memory including access logs."""
        await super().clear()
        self._access_log.clear()
        logger.info("AutoMemory: all memory cleared")
