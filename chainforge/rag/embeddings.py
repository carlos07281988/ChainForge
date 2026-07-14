"""Embedding providers for the RAG pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("rag.embeddings")


class OpenAIEmbedding(BaseModel):
    """OpenAI embedding provider.

    Requires the ``openai`` package and ``OPENAI_API_KEY`` env var.

    Args:
        model: Embedding model name (default text-embedding-3-small).
        dimensions: Output dimensions (default 1536).
    """

    model: str = Field(default="text-embedding-3-small")
    dimensions: int = Field(default=1536)
    _client: Any = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the OpenAI API."""
        try:
            import openai
        except ImportError:
            raise ImportError("OpenAI package required. Install: pip install openai")

        client = openai.AsyncOpenAI()
        resp = await client.embeddings.create(model=self.model, input=texts, dimensions=self.dimensions)
        return [d.embedding for d in resp.data]

    async def embed_one(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0] if results else []


# Re-export the EmbeddingFunction protocol from memory for convenience
from chainforge.memory.embedding import EmbeddingFunction, IdentityEmbedding, cosine_similarity  # noqa: E402, F401

__all__ = ["OpenAIEmbedding", "EmbeddingFunction", "IdentityEmbedding", "cosine_similarity"]
