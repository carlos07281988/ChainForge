"""Embedding function protocol — convert text to vector embeddings."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Protocol

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("memory.embedding")


class EmbeddingFunction(Protocol):
    """Protocol for converting text to vector embeddings.

    Implementations:
      - IdentityEmbedding: simple hash-based (development only)
      - OpenAIEmbedding: uses OpenAI API
    """

    dim: int = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        ...

    async def embed_one(self, text: str) -> list[float]:
        """Embed a single text."""
        results = await self.embed([text])
        return results[0] if results else []


# ── Simple hash-based embedding (for development / testing) ────────────────


class IdentityEmbedding(BaseModel):
    """Simple hash-based embedding for development use.

    Not semantically meaningful — use only for testing or when
    no embedding API is available. Produces 64-dimensional vectors.
    """

    dim: int = Field(default=64, description="Embedding dimension")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(t) for t in texts]

    async def embed_one(self, text: str) -> list[float]:
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> list[float]:
        """Create a deterministic pseudo-embedding from text hash.

        Uses MD5 to produce reproducible vectors for the same text.
        This is NOT semantically meaningful — use a real embedding
        model for production.
        """
        h = hashlib.md5(text.encode()).digest()
        # Expand hash to fill dim dimensions using repeated hashing
        result = []
        seed = text
        for i in range(self.dim):
            h = hashlib.md5(f"{seed}:{i}".encode()).digest()
            val = int.from_bytes(h[:4], "big") / 2**32
            result.append(val * 2 - 1)  # Normalize to [-1, 1]
        return result


# ── Cosine similarity ─────────────────────────────────────────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
