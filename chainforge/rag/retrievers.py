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
"""Retrievers — fetch relevant documents for a query."""

from __future__ import annotations

from typing import Any, Protocol

from chainforge.rag.documents import Document
from chainforge.logging import get_logger
from chainforge.rag.vectorstores import InMemoryVectorStore, VectorStore

logger = get_logger("rag.retrievers")


class Retriever(Protocol):
    """Protocol for document retrievers."""

    async def get_relevant_documents(self, query: str) -> list[Document]:
        """Retrieve documents relevant to the query."""
        ...


class VectorStoreRetriever:
    """Retriever backed by a VectorStore.

    Args:
        vector_store: The vector store to search.
        k: Number of documents to retrieve (default 4).
        score_threshold: Minimum similarity score (default 0.0).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        k: int = 4,
        score_threshold: float = 0.0,
    ):
        self.vector_store = vector_store
        self.k = k
        self.score_threshold = score_threshold

    async def get_relevant_documents(self, query: str) -> list[Document]:
        """Retrieve documents by vector similarity."""
        results = await self.vector_store.similarity_search(query, k=self.k * 2)
        filtered = [d for d in results if d.metadata.get("score", 1.0) >= self.score_threshold]
        return filtered[:self.k]


class MultiQueryRetriever:
    """Retriever that generates multiple query variations and aggregates results.

    Args:
        retriever: Base retriever to use.
        llm: LLM for generating query variations.
        n_queries: Number of query variations (default 3).
    """

    def __init__(self, retriever: Retriever, llm: Any | None = None, n_queries: int = 3):
        self._retriever = retriever
        self._llm = llm
        self.n_queries = n_queries

    async def get_relevant_documents(self, query: str) -> list[Document]:
        """Generate query variations and aggregate results."""
        queries = [query]
        if self._llm:
            variations = await self._generate_variations(query)
            queries.extend(variations[:self.n_queries - 1])

        all_docs = []
        seen = set()
        for q in queries:
            docs = await self._retriever.get_relevant_documents(q)
            for d in docs:
                key = d.page_content[:100]
                if key not in seen:
                    seen.add(key)
                    all_docs.append(d)
        return all_docs

    async def _generate_variations(self, query: str) -> list[str]:
        """Generate query variations using the LLM."""
        try:
            from chainforge.core.message import Message, Role
            prompt = (
                f"Generate {self.n_queries - 1} alternative phrasings of the following question. "
                f"Return each on a new line without numbering.\nQuestion: {query}"
            )
            response = await self._llm.generate([Message(role=Role.user, content=prompt)])
            if response.content:
                return [line.strip() for line in response.content.strip().split("\n") if line.strip()]
        except Exception as e:
            logger.warning(f"Query generation failed: {e}")
        return []
