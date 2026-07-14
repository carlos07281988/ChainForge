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

# ── Chroma Vector Store ──────────────────────────────────────────────────


class ChromaVectorStore:
    """ChromaDB vector store backend.

    Requires the ``chromadb`` package.

    Args:
        collection_name: Collection name (default "chainforge").
        embedding_fn: Embedding function for document/query encoding.
        persist_directory: Optional path for persistent storage.
    """

    def __init__(
        self,
        collection_name: str = "chainforge",
        embedding_fn: EmbeddingFunction | None = None,
        persist_directory: str | None = None,
    ):
        self.collection_name = collection_name
        self._embedding_fn = embedding_fn or IdentityEmbedding(dim=64)
        self._collection = None
        self._persist_directory = persist_directory

    async def _ensure_collection(self):
        if self._collection is not None:
            return
        import chromadb
        from chromadb.config import Settings
        client = chromadb.Client(Settings(
            persist_directory=self._persist_directory,
            anonymized_telemetry=False,
        ))
        self._collection = client.get_or_create_collection(self.collection_name)

    async def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> list[str]:
        await self._ensure_collection()
        texts = [d.page_content for d in documents]
        if embeddings is None:
            embeddings = await self._embedding_fn.embed(texts)
        ids = [str(uuid.uuid4()) for _ in documents]
        metadatas = [d.metadata for d in documents]
        self._collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        return ids

    async def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        await self._ensure_collection()
        query_emb = (await self._embedding_fn.embed([query]))[0]
        results = self._collection.query(query_embeddings=[query_emb], n_results=k)
        docs = []
        if results["documents"]:
            for i, text in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                docs.append(Document(page_content=text, metadata=meta))
        return docs

    async def similarity_search_by_vector(self, embedding: list[float], k: int = 4) -> list[Document]:
        await self._ensure_collection()
        results = self._collection.query(query_embeddings=[embedding], n_results=k)
        docs = []
        if results["documents"]:
            for i, text in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                docs.append(Document(page_content=text, metadata=meta))
        return docs


# ── FAISS Vector Store ────────────────────────────────────────────────────


class FAISSVectorStore:
    """FAISS vector store backend (in-memory).

    Requires the ``faiss`` and ``numpy`` packages.

    Args:
        embedding_fn: Embedding function for document/query encoding.
    """

    def __init__(self, embedding_fn: EmbeddingFunction | None = None):
        self._embedding_fn = embedding_fn or IdentityEmbedding(dim=64)
        self._documents: list[Document] = []
        self._embeddings: list[list[float]] = []
        self._index = None

    async def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> list[str]:
        import numpy as np
        ids = [str(uuid.uuid4()) for _ in documents]
        texts = [d.page_content for d in documents]
        if embeddings is None:
            embeddings = await self._embedding_fn.embed(texts)
        self._documents.extend(documents)
        self._embeddings.extend(embeddings)
        emb_array = np.array(embeddings, dtype=np.float32)
        if self._index is None:
            import faiss
            dim = emb_array.shape[1]
            self._index = faiss.IndexFlatIP(dim)
        self._index.add(emb_array)
        return ids

    async def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        import numpy as np
        query_emb = (await self._embedding_fn.embed([query]))[0]
        return await self.similarity_search_by_vector(query_emb, k=k)

    async def similarity_search_by_vector(self, embedding: list[float], k: int = 4) -> list[Document]:
        if self._index is None or self._index.ntotal == 0:
            return []
        import numpy as np
        k = min(k, self._index.ntotal)
        query_array = np.array([embedding], dtype=np.float32)
        scores, indices = self._index.search(query_array, k)
        results = []
        for i, idx in enumerate(indices[0]):
            doc = self._documents[idx].model_copy(deep=True)
            doc.metadata["score"] = float(scores[0][i])
            results.append(doc)
        return results

    @property
    def count(self) -> int:
        return len(self._documents)
