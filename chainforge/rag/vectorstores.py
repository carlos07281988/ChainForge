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


# ── Pinecone Vector Store ────────────────────────────────────────────────


class PineconeVectorStore:
    """Pinecone vector store backend.

    Requires the ``pinecone`` package and PINECONE_API_KEY environment variable.

    Args:
        index_name: Pinecone index name.
        embedding_fn: Embedding function for document/query encoding.
        namespace: Optional namespace for partitioning.
    """

    def __init__(
        self,
        index_name: str = "chainforge",
        embedding_fn: EmbeddingFunction | None = None,
        namespace: str | None = None,
    ):
        self.index_name = index_name
        self._embedding_fn = embedding_fn or IdentityEmbedding(dim=384)
        self.namespace = namespace
        self._index = None

    async def _ensure_index(self):
        if self._index is not None:
            return
        import os
        import pinecone
        pc = pinecone.Pinecone(api_key=os.environ.get("PINECONE_API_KEY", ""))
        if self.index_name not in pc.list_indexes().names():
            pc.create_index(name=self.index_name, dimension=self._embedding_fn.dim, metric="cosine")
        self._index = pc.Index(self.index_name)

    async def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> list[str]:
        await self._ensure_index()
        texts = [d.page_content for d in documents]
        if embeddings is None:
            embeddings = await self._embedding_fn.embed(texts)
        ids = [str(uuid.uuid4()) for _ in documents]
        vectors = []
        for i, doc in enumerate(documents):
            vectors.append({
                "id": ids[i],
                "values": embeddings[i],
                "metadata": {"text": doc.page_content[:2000], **doc.metadata},
            })
        self._index.upsert(vectors=vectors, namespace=self.namespace or "")
        return ids

    async def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        await self._ensure_index()
        query_emb = (await self._embedding_fn.embed([query]))[0]
        return await self.similarity_search_by_vector(query_emb, k=k)

    async def similarity_search_by_vector(self, embedding: list[float], k: int = 4) -> list[Document]:
        await self._ensure_index()
        result = self._index.query(vector=embedding, top_k=k, include_metadata=True, namespace=self.namespace or "")
        docs = []
        for match in result.matches:
            text = match.metadata.pop("text", "") if match.metadata else ""
            meta = dict(match.metadata) if match.metadata else {}
            meta["score"] = match.score or 0.0
            docs.append(Document(page_content=text, metadata=meta))
        return docs


# ── Qdrant Vector Store ──────────────────────────────────────────────────


class QdrantVectorStore:
    """Qdrant vector store backend.

    Requires the ``qdrant-client`` package.

    Args:
        collection_name: Qdrant collection name.
        embedding_fn: Embedding function for document/query encoding.
        url: Qdrant server URL (default: http://localhost:6333).
        api_key: Qdrant API key.
    """

    def __init__(
        self,
        collection_name: str = "chainforge",
        embedding_fn: EmbeddingFunction | None = None,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
    ):
        self.collection_name = collection_name
        self._embedding_fn = embedding_fn or IdentityEmbedding(dim=384)
        self.url = url
        self.api_key = api_key
        self._client = None

    async def _ensure_collection(self):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        if self._client is not None:
            return
        self._client = QdrantClient(url=self.url, api_key=self.api_key)
        collections = self._client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=self._embedding_fn.dim, distance=models.Distance.COSINE),
            )

    async def add_documents(self, documents: list[Document], embeddings: list[list[float]] | None = None) -> list[str]:
        from qdrant_client.http import models
        await self._ensure_collection()
        texts = [d.page_content for d in documents]
        if embeddings is None:
            embeddings = await self._embedding_fn.embed(texts)
        ids = [str(uuid.uuid4()) for _ in documents]
        points = []
        for i, doc in enumerate(documents):
            points.append(models.PointStruct(
                id=ids[i],
                vector=embeddings[i],
                payload={"text": doc.page_content, **doc.metadata},
            ))
        self._client.upsert(collection_name=self.collection_name, points=points)
        return ids

    async def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        await self._ensure_collection()
        query_emb = (await self._embedding_fn.embed([query]))[0]
        return await self.similarity_search_by_vector(query_emb, k=k)

    async def similarity_search_by_vector(self, embedding: list[float], k: int = 4) -> list[Document]:
        from qdrant_client.http import models
        await self._ensure_collection()
        result = self._client.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            limit=k,
        )
        docs = []
        for scored_point in result:
            payload = dict(scored_point.payload) if scored_point.payload else {}
            text = payload.pop("text", "")
            meta = payload
            meta["score"] = scored_point.score or 0.0
            docs.append(Document(page_content=text, metadata=meta))
        return docs
