"""Vector store abstraction — store and retrieve document embeddings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from chainforge.memory.embedding import EmbeddingFunction, IdentityEmbedding, cosine_similarity
from chainforge.rag.documents import Document


class VectorStore(Protocol):
    """Protocol for vector stores."""

    async def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> list[str]:
        """Add documents to the store.

        Returns:
            List of document IDs.
        """
        ...

    async def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        """Search for similar documents by query text."""
        ...

    async def similarity_search_by_vector(self, embedding: list[float], k: int = 4) -> list[Document]:
        """Search for similar documents by embedding vector."""
        ...


@dataclass
class _VectorStoreEntry:
    id: str
    document: Document
    embedding: list[float]


class InMemoryVectorStore:
    """In-memory vector store for development and testing.

    Args:
        embedding_fn: Embedding function for query encoding.
    """

    def __init__(self, embedding_fn: EmbeddingFunction | None = None):
        self._entries: list[_VectorStoreEntry] = []
        self._embedding_fn = embedding_fn or IdentityEmbedding(dim=64)

    async def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> list[str]:
        """Add documents to the store.

        Args:
            documents: Documents to add.
            embeddings: Pre-computed embeddings (computed if None).

        Returns:
            List of document IDs.
        """
        if embeddings is None:
            texts = [d.page_content for d in documents]
            embeddings = await self._embedding_fn.embed(texts)

        ids = []
        for doc, emb in zip(documents, embeddings):
            eid = str(uuid.uuid4())
            self._entries.append(_VectorStoreEntry(id=eid, document=doc, embedding=emb))
            ids.append(eid)
        return ids

    async def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        """Search for documents similar to query text."""
        query_emb = (await self._embedding_fn.embed([query]))[0]
        return await self.similarity_search_by_vector(query_emb, k=k)

    async def similarity_search_by_vector(self, embedding: list[float], k: int = 4) -> list[Document]:
        """Search for documents by embedding vector."""
        scored = []
        for entry in self._entries:
            score = cosine_similarity(embedding, entry.embedding)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]

        results = []
        for score, entry in top:
            doc = entry.document.model_copy(deep=True)
            doc.metadata["score"] = round(score, 4)
            results.append(doc)
        return results

    @property
    def count(self) -> int:
        return len(self._entries)
