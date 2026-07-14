"""Vector memory — semantic retrieval over past conversations."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

import logging
from chainforge.logging import get_logger, log_data
from chainforge.memory.embedding import EmbeddingFunction, IdentityEmbedding, cosine_similarity

logger = get_logger("memory.vector")



@dataclass
class MemoryEntry:
    """A single entry in the vector memory store."""

    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


class VectorMemory(BaseModel):
    """Semantic memory that stores and retrieves via vector similarity.

    Usage:
        memory = VectorMemory(embedding_fn=IdentityEmbedding(dim=64))

        # Store messages
        await memory.add("The user likes Python 3.12")
        await memory.add("The user prefers async patterns")

        # Retrieve semantically related content
        results = await memory.query("What language does the user prefer?")
        for entry in results:
            print(entry.text, entry.score)
    """

    embedding_fn: Any = Field(default_factory=lambda: IdentityEmbedding(dim=64))
    store: list = Field(default_factory=list, description="In-memory entry store")

    model_config = {"arbitrary_types_allowed": True}

    @property
    def dim(self) -> int:
        return self.embedding_fn.dim

    async def add(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        *,
        embedding: list[float] | None = None,
    ) -> str:
        """Add a text entry to the memory store.

        Args:
            text: The text content to store.
            metadata: Optional metadata (e.g., {"role": "user", "session": "abc"}).
            embedding: Pre-computed embedding. If None, computed automatically.

        Returns:
            Entry ID.
        """
        if embedding is None:
            results = await self.embedding_fn.embed([text])
            embedding = results[0]

        entry_id = str(uuid.uuid4())
        entry = MemoryEntry(
            id=entry_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.store.append(entry)
        log_data(logger, logging.DEBUG, f"Stored entry {entry_id}", data={"text_len": len(text)})
        return entry_id

    async def add_many(
        self,
        items: list[tuple[str, dict[str, Any] | None]],
    ) -> list[str]:
        """Add multiple text entries at once (batched embedding).

        Args:
            items: List of (text, metadata) tuples.

        Returns:
            List of entry IDs.
        """
        texts = [item[0] for item in items]
        embeddings = await self.embedding_fn.embed(texts)
        ids = []
        for (text, metadata), emb in zip(items, embeddings):
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                text=text,
                embedding=emb,
                metadata=metadata or {},
            )
            self.store.append(entry)
            ids.append(entry.id)
        log_data(logger, logging.DEBUG, f"Stored {len(ids)} entries", data={"count": len(ids)})
        return ids

    async def query(
        self,
        text: str,
        k: int = 5,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve semantically similar entries.

        Args:
            text: Query text.
            k: Maximum number of results.
            min_score: Minimum similarity score [0, 1].
            filter_metadata: Only return entries matching these metadata key/values.

        Returns:
            List of {"id", "text", "metadata", "timestamp", "score"} dicts.
        """
        if not self.store:
            return []

        query_emb = (await self.embedding_fn.embed([text]))[0]

        # Score all entries
        scored = []
        for entry in self.store:
            if filter_metadata:
                if not all(entry.metadata.get(k) == v for k, v in filter_metadata.items()):
                    continue
            score = cosine_similarity(query_emb, entry.embedding)
            if score >= min_score:
                scored.append((score, entry))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id": entry.id,
                "text": entry.text,
                "metadata": entry.metadata,
                "timestamp": entry.timestamp,
                "score": round(score, 4),
            }
            for score, entry in scored[:k]
        ]

    async def remove(self, entry_id: str) -> bool:
        """Remove an entry by ID.

        Returns:
            True if removed, False if not found.
        """
        for i, entry in enumerate(self.store):
            if entry.id == entry_id:
                self.store.pop(i)
                return True
        return False

    async def clear(self) -> None:
        """Remove all entries."""
        self.store.clear()
        log_data(logger, logging.INFO, "Cleared vector memory")

    @property
    def size(self) -> int:
        return len(self.store)

    def stats(self) -> dict[str, Any]:
        """Return usage statistics."""
        return {
            "size": self.size,
            "dim": self.dim,
            "type": type(self.embedding_fn).__name__,
        }
