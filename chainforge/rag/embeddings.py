# Copyright 2024 ChainForge Contributors
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


class HuggingFaceEmbedding(BaseModel):
    """HuggingFace embedding provider using sentence-transformers.

    Requires the ``sentence-transformers`` package.

    Args:
        model_name: HuggingFace model name (default all-MiniLM-L6-v2).
    """

    model_name: str = Field(default="all-MiniLM-L6-v2")
    _model: Any = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("sentence-transformers required. Install: pip install sentence-transformers")

        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        embeddings = self._model.encode(texts)
        return [e.tolist() for e in embeddings]

    async def embed_one(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0] if results else []

    @property
    def dim(self) -> int:
        return 384  # all-MiniLM-L6-v2 dimension


class GoogleEmbedding(BaseModel):
    """Google Gemini embedding provider.

    Requires the ``google-generativeai`` package and ``GOOGLE_API_KEY`` env var.

    Args:
        model: Embedding model (default text-embedding-004).
    """

    model: str = Field(default="text-embedding-004")
    _client: Any = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai required. Install: pip install google-generativeai")

        genai.configure()
        results = []
        for t in texts:
            result = genai.embed_content(model=self.model, content=t)
            results.append(result["embedding"])
        return results

    async def embed_one(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0] if results else []

__all__ = ["OpenAIEmbedding", "HuggingFaceEmbedding", "GoogleEmbedding", "EmbeddingFunction", "IdentityEmbedding", "cosine_similarity"]
