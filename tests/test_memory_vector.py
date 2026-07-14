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
"""Tests for memory 2.0 (embedding, vector memory, memory manager)."""

import pytest

from chainforge.memory.embedding import IdentityEmbedding, cosine_similarity
from chainforge.memory.vector import VectorMemory
from chainforge.memory.manager import MemoryManager
from chainforge.memory.buffer import BufferMemory


class TestIdentityEmbedding:
    @pytest.mark.asyncio
    async def test_embed_consistency(self):
        emb = IdentityEmbedding(dim=64)
        v1 = await emb.embed_one("hello world")
        v2 = await emb.embed_one("hello world")
        assert len(v1) == 64
        assert v1 == v2  # deterministic

    @pytest.mark.asyncio
    async def test_embed_different_texts(self):
        emb = IdentityEmbedding(dim=64)
        v1 = await emb.embed_one("cat")
        v2 = await emb.embed_one("dog")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_batch_embed(self):
        emb = IdentityEmbedding(dim=32)
        results = await emb.embed(["a", "b", "c"])
        assert len(results) == 3
        assert all(len(v) == 32 for v in results)


class TestCosineSimilarity:
    def test_identical(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_opposite(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_orthogonal(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_dim_mismatch(self):
        import pytest
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 0.0], [1.0])

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)


class TestVectorMemory:
    @pytest.mark.asyncio
    async def test_add_and_query(self):
        mem = VectorMemory(embedding_fn=IdentityEmbedding(dim=64))
        await mem.add("The user likes Python programming")
        await mem.add("The user prefers async patterns")
        await mem.add("The user lives in Beijing")

        results = await mem.query("What language does the user like?", k=2)
        assert len(results) >= 1
        # The identity embedding is hash-based, so semantic results vary,
        # but the structure should be correct
        assert all("id" in r for r in results)
        assert all("text" in r for r in results)
        assert all("score" in r for r in results)

    @pytest.mark.asyncio
    async def test_query_empty(self):
        mem = VectorMemory()
        results = await mem.query("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_add_many(self):
        mem = VectorMemory(embedding_fn=IdentityEmbedding(dim=32))
        ids = await mem.add_many([
            ("entry 1", {"tag": "a"}),
            ("entry 2", {"tag": "b"}),
            ("entry 3", {"tag": "a"}),
        ])
        assert len(ids) == 3
        assert mem.size == 3

    @pytest.mark.asyncio
    async def test_filter_metadata(self):
        mem = VectorMemory(embedding_fn=IdentityEmbedding(dim=32))
        await mem.add("Python is great", {"topic": "python"})
        await mem.add("TypeScript is also great", {"topic": "typescript"})
        await mem.add("I love programming", {"topic": "python"})

        results = await mem.query("programming", k=10, filter_metadata={"topic": "python"})
        assert len(results) >= 2
        assert all(r["metadata"]["topic"] == "python" for r in results)

    @pytest.mark.asyncio
    async def test_remove(self):
        mem = VectorMemory(embedding_fn=IdentityEmbedding(dim=32))
        eid = await mem.add("test entry")
        assert mem.size == 1
        assert await mem.remove(eid) is True
        assert mem.size == 0
        assert await mem.remove("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear(self):
        mem = VectorMemory(embedding_fn=IdentityEmbedding(dim=32))
        await mem.add("entry 1")
        await mem.add("entry 2")
        assert mem.size == 2
        await mem.clear()
        assert mem.size == 0

    @pytest.mark.asyncio
    async def test_stats(self):
        mem = VectorMemory(embedding_fn=IdentityEmbedding(dim=64))
        await mem.add("test")
        stats = mem.stats()
        assert stats["size"] == 1
        assert stats["dim"] == 64


class TestMemoryManager:
    @pytest.mark.asyncio
    async def test_creation(self):
        mgr = MemoryManager(
            working=BufferMemory(max_messages=5),
            episodic=VectorMemory(embedding_fn=IdentityEmbedding(dim=32)),
        )
        assert mgr.working is not None
        assert mgr.episodic is not None

    @pytest.mark.asyncio
    async def test_store_and_get_context(self):
        mgr = MemoryManager(
            working=BufferMemory(max_messages=10),
        )

        await mgr.store("Hello, I am Alice", {"role": "user"})
        context = await mgr.get_context("Who is there?")
        assert "Alice" in context or "Alice" in str(mgr.working.messages)

    @pytest.mark.asyncio
    async def test_remember_semantic(self):
        mgr = MemoryManager(
            working=BufferMemory(max_messages=5),
        )

        await mgr.remember("The user prefers dark mode")
        context = await mgr.get_context("What theme?")
        assert context is not None

    @pytest.mark.asyncio
    async def test_stats(self):
        mgr = MemoryManager(working=BufferMemory(max_messages=10))
        stats = mgr.stats()
        assert "working" in stats

    @pytest.mark.asyncio
    async def test_clear(self):
        mgr = MemoryManager(working=BufferMemory(max_messages=10))
        await mgr.clear()
        assert len(mgr.working.messages) == 0
