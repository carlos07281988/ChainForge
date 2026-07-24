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
"""Agent Memory Consolidation — periodic review, scoring, pruning, and compression.

Simulates human memory consolidation:
  - Review: score memories by recency, frequency, and consistency
  - Prune: remove low-confidence memories
  - Compress: merge related memories into summaries
  - Report: statistics and identified patterns

Usage:
    from chainforge.core.consolidation import MemoryConsolidator, ConsolidationConfig

    consolidator = MemoryConsolidator(
        config=ConsolidationConfig(confidence_threshold=0.3)
    )

    memories = ["User likes Python", "User works at Google", ...]
    report = consolidator.consolidate(memories)
    # {"reviewed": 50, "pruned": 12, "compressed": 5, "remaining": 33, "patterns": [...]}
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("core.consolidation")


# ── Configuration ─────────────────────────────────────────────────────────


class ConsolidationConfig(BaseModel):
    """Configuration for memory consolidation behavior."""

    confidence_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Memories below this confidence score are pruned",
    )
    max_memories: int = Field(
        default=500,
        description="Max memories before consolidation is triggered",
    )
    enable_compression: bool = Field(
        default=True,
        description="Merge related memories into summaries",
    )
    llm_assisted: bool = Field(
        default=False,
        description="Use LLM for pattern extraction and compression",
    )
    recency_weight: float = Field(
        default=0.4, ge=0.0, le=1.0,
        description="Weight of recency in confidence scoring",
    )
    frequency_weight: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Weight of access frequency in confidence scoring",
    )
    quality_weight: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Weight of content quality in confidence scoring",
    )


# ── MemoryConsolidator ─────────────────────────────────────────────────────


class MemoryConsolidator:
    """Orchestrates memory consolidation: review → prune → compress → report.

    Works standalone (with a list of memory strings) or integrated with
    AutoMemoryManager.

    Usage:
        # Standalone
        consolidator = MemoryConsolidator()
        report = consolidator.consolidate(["mem1", "mem2", ...])

        # With AutoMemoryManager
        report = await consolidator.consolidate_manager(memory_manager)
    """

    def __init__(self, config: ConsolidationConfig | None = None):
        self._config = config or ConsolidationConfig()
        self._access_counts: dict[int, int] = {}  # memory index → access count
        self._creation_times: dict[int, float] = {}  # memory index → timestamp

    @property
    def config(self) -> ConsolidationConfig:
        return self._config

    # ── Confidence scoring ──────────────────────────────────────────────

    def _score_memory(self, memory: str, index: int) -> float:
        """Compute a confidence score for a single memory.

        Score components:
          - Recency: newer → higher (based on index position)
          - Frequency: more accessed → higher
          - Quality: longer, more detailed → higher

        Returns:
            Float in [0.0, 1.0].
        """
        cfg = self._config

        # Recency score: more recent memories (higher index) score higher
        # If we don't have timestamps, use a simple decay
        now = time.time()
        created = self._creation_times.get(index, now)
        age_hours = (now - created) / 3600
        recency = max(0.0, 1.0 - age_hours / 168.0)  # Decay over 7 days

        # Frequency score
        freq = self._access_counts.get(index, 0)
        frequency = min(1.0, freq / 10.0)  # Cap at 10 accesses

        # Quality score: based on content
        quality = self._score_quality(memory)

        # Weighted combination
        score = (
            cfg.recency_weight * recency
            + cfg.frequency_weight * frequency
            + cfg.quality_weight * quality
        )
        return max(0.0, min(1.0, score))

    def _score_quality(self, memory: str) -> float:
        """Score the quality of a memory based on content features."""
        if not memory or not memory.strip():
            return 0.0

        score = 0.3  # Base score for any non-empty memory

        # Length bonus: longer memories tend to be more informative
        words = memory.split()
        if len(words) > 20:
            score += 0.2
        elif len(words) > 10:
            score += 0.1
        elif len(words) > 5:
            score += 0.05

        # Specificity bonus: memories with specific details score higher
        if re.search(r'\d+', memory):  # Contains numbers
            score += 0.1
        if any(c in memory for c in '"\''):  # Contains quotes
            score += 0.1
        if re.search(r'\b([A-Z][a-z]+)\b', memory):  # Has proper nouns
            score += 0.1
        if ',' in memory:  # Has multiple details
            score += 0.1

        # Cap at 1.0
        return min(1.0, score)

    def _find_related(self, memories: list[str]) -> list[list[int]]:
        """Group related memories by keyword overlap.

        Returns:
            List of groups, each group is a list of memory indices.
        """
        # Tokenize each memory
        tokenized = []
        for mem in memories:
            tokens = set(
                w.lower() for w in mem.split()
                if len(w) > 3 and w.lower() not in {
                    "this", "that", "with", "from", "have", "been",
                    "were", "what", "when", "where", "which",
                }
            )
            tokenized.append(tokens)

        # Group by Jaccard similarity > 0.2
        groups: list[list[int]] = []
        assigned: set[int] = set()

        for i in range(len(memories)):
            if i in assigned:
                continue
            group = [i]
            for j in range(i + 1, len(memories)):
                if j in assigned:
                    continue
                # Jaccard similarity
                if not tokenized[i] or not tokenized[j]:
                    continue
                intersection = len(tokenized[i] & tokenized[j])
                union = len(tokenized[i] | tokenized[j])
                if union > 0 and intersection / union > 0.2:
                    group.append(j)
                    assigned.add(j)
            if len(group) > 1:
                groups.append(group)
            assigned.add(i)

        return groups

    # ── Core operations ─────────────────────────────────────────────────

    def review(self, memories: list[str]) -> dict[int, float]:
        """Score all memories and return confidence scores.

        Args:
            memories: List of memory strings.

        Returns:
            Dict mapping memory index → confidence score.
        """
        scores: dict[int, float] = {}
        for i, mem in enumerate(memories):
            scores[i] = self._score_memory(mem, i)
        return scores

    def prune(self, memories: list[str],
              scores: dict[int, float] | None = None,
              threshold: float | None = None) -> tuple[list[str], list[int]]:
        """Remove low-confidence memories.

        Args:
            memories: Original list of memories.
            scores: Dict of index → score (computed if None).
            threshold: Confidence threshold (uses config if None).

        Returns:
            (kept_memories, pruned_indices).
        """
        if scores is None:
            scores = self.review(memories)
        threshold = threshold if threshold is not None else self._config.confidence_threshold

        kept: list[str] = []
        pruned: list[int] = []
        for i, mem in enumerate(memories):
            if scores.get(i, 0.0) >= threshold:
                kept.append(mem)
            else:
                pruned.append(i)

        return kept, pruned

    def compress(self, memories: list[str],
                 llm: Any | None = None) -> tuple[list[str], list[dict[str, Any]]]:
        """Merge related memories into summaries.

        Args:
            memories: List of memory strings.
            llm: Optional LLM for intelligent compression.

        Returns:
            (compressed_memories, compression_events) where compression_events
            describes what was merged.
        """
        if not self._config.enable_compression:
            return list(memories), []

        groups = self._find_related(memories)
        compressed: list[str] = []
        compressed_indices: set[int] = set()
        events: list[dict[str, Any]] = []

        for group in groups:
            original_texts = [memories[i] for i in group]
            # Simple merge: concatenate with separator
            if len(original_texts) <= 3:
                summary = "; ".join(original_texts)
            else:
                # For larger groups, take the most representative memories
                key_memories = original_texts[:3]
                summary = "; ".join(key_memories)
                summary += f" (and {len(original_texts) - 3} more related items)"

            compressed.append(summary)
            for i in group:
                compressed_indices.add(i)
            events.append({
                "source_indices": group,
                "source_texts": original_texts,
                "summary": summary,
            })

        # Add ungrouped memories
        result = list(memories)
        # Replace grouped memories with their summaries
        result = [m for i, m in enumerate(memories) if i not in compressed_indices]
        result.extend(compressed)

        return result, events

    def consolidate(self, memories: list[str],
                    llm: Any | None = None) -> dict[str, Any]:
        """Run the full consolidation pipeline: review → prune → compress.

        Args:
            memories: List of memory strings.
            llm: Optional LLM for LLM-assisted mode.

        Returns:
            Report dict with reviewed, pruned, compressed, remaining counts,
            and patterns discovered.
        """
        logger.info(f"Consolidating {len(memories)} memories")

        # 1. Review & score
        scores = self.review(memories)

        # 2. Prune
        kept, pruned_indices = self.prune(memories, scores)

        # 3. Compress
        final_memories, compression_events = self.compress(kept, llm)

        # 4. Extract patterns
        patterns = self._extract_patterns(memories, scores)

        # 5. Build report
        report = {
            "reviewed": len(memories),
            "pruned": len(pruned_indices),
            "compressed": len(compression_events),
            "remaining": len(final_memories),
            "retention_rate": round(len(final_memories) / max(1, len(memories)), 3),
            "patterns": patterns,
            "pruned_indices": pruned_indices,
            "compression_events": compression_events,
        }

        avg_score = sum(scores.values()) / max(1, len(scores))
        report["avg_confidence"] = round(avg_score, 3)

        logger.info(
            f"Consolidation done: {report['reviewed']} reviewed, "
            f"{report['pruned']} pruned, {report['compressed']} compressed, "
            f"{report['remaining']} remaining"
        )
        return report

    def _extract_patterns(self, memories: list[str],
                           scores: dict[int, float]) -> list[dict[str, Any]]:
        """Extract common patterns/themes from memories."""
        if not memories:
            return []

        # Count common keywords
        all_words: list[str] = []
        for mem in memories:
            words = [w.lower() for w in mem.split() if len(w) > 3
                     and w.lower() not in {"this", "that", "with", "from",
                                            "have", "been", "were", "what"}]
            all_words.extend(words)

        if not all_words:
            return []

        word_counts = Counter(all_words)
        top_keywords = word_counts.most_common(10)

        patterns = []
        for word, count in top_keywords:
            related = [mem for mem in memories if word in mem.lower()]
            if related:
                patterns.append({
                    "keyword": word,
                    "frequency": count,
                    "occurrences": len(related),
                    "example": related[0][:100],
                })

        return patterns

    def record_access(self, memory_index: int) -> None:
        """Record an access to a memory (for frequency tracking)."""
        self._access_counts[memory_index] = self._access_counts.get(memory_index, 0) + 1

    def record_creation(self, memory_index: int) -> None:
        """Record the creation time of a memory (for recency tracking)."""
        self._creation_times[memory_index] = time.time()

    # ── AutoMemoryManager integration ───────────────────────────────────

    async def consolidate_manager(self, memory_manager: Any) -> dict[str, Any]:
        """Consolidate memories in an AutoMemoryManager.

        Extracts memories from the manager, consolidates, and updates.

        Args:
            memory_manager: An AutoMemoryManager (or similar) instance.

        Returns:
            Consolidation report.
        """
        # Extract memories from the manager
        memories = self._extract_from_manager(memory_manager)
        if not memories:
            return {"reviewed": 0, "pruned": 0, "compressed": 0, "remaining": 0}

        report = self.consolidate(memories)

        # Apply pruning to the manager if we have indices
        if report["pruned"] > 0:
            self._apply_prune(memory_manager, report["pruned_indices"])

        # Apply compression if enabled
        if report["compressed"] > 0 and self._config.enable_compression:
            self._apply_compression(memory_manager, report["compression_events"])

        return report

    def _extract_from_manager(self, manager: Any) -> list[str]:
        """Extract memory strings from a memory manager."""
        memories: list[str] = []

        # Try AutoMemoryManager / MemoryManager interface
        if hasattr(manager, "working_memory") and isinstance(manager.working_memory, list):
            for item in manager.working_memory:
                if isinstance(item, str):
                    memories.append(item)
                elif hasattr(item, "content"):
                    memories.append(item.content)
                elif isinstance(item, dict):
                    memories.append(item.get("content", str(item)))

        # Try buffer interface
        if hasattr(manager, "get_recent"):
            recent = manager.get_recent(100) if callable(manager.get_recent) else manager.get_recent
            if isinstance(recent, list):
                for item in recent:
                    if isinstance(item, str):
                        memories.append(item)

        # Try vector store interface
        if hasattr(manager, "all_entries"):
            entries = manager.all_entries
            for entry in entries:
                if isinstance(entry, str):
                    memories.append(entry)
                elif isinstance(entry, dict):
                    memories.append(entry.get("text", entry.get("content", str(entry))))

        return memories

    def _apply_prune(self, manager: Any, pruned_indices: list[int]) -> None:
        """Remove pruned memories from the manager."""
        if hasattr(manager, "remove_by_indices") and callable(manager.remove_by_indices):
            manager.remove_by_indices(pruned_indices)
        elif hasattr(manager, "prune") and callable(manager.prune):
            manager.prune(indices=pruned_indices)

    def _apply_compression(self, manager: Any,
                            compression_events: list[dict[str, Any]]) -> None:
        """Store compression summaries in the manager."""
        for event in compression_events:
            summary = event.get("summary", "")
            if summary and hasattr(manager, "store") and callable(manager.store):
                import inspect
                try:
                    manager.store(summary, {"type": "compressed", "sources": event.get("source_indices", [])})
                except Exception:
                    pass


__all__ = [
    "ConsolidationConfig",
    "MemoryConsolidator",
]
