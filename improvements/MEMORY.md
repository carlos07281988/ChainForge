# Memory 2.0 (Vector Memory)

> 为 ChainForge 添加基于语义检索的向量记忆系统

## Motivation

当前记忆系统只有两种：
- `BufferMemory` — 滑动窗口保留最近 N 轮对话
- `SummaryMemory` — 名不副实，实际上只是滚动窗口

但 Agent 需要的是：

1. **语义检索** — 从大量历史中找到相关的对话片段
2. **持久化** — 跨 session、跨重启保留记忆
3. **分层** — 工作记忆 → 情景记忆 → 语义记忆

---

## Design

### Embedding Protocol

```python
class EmbeddingFunction(Protocol):
    """Convert text to vector embeddings."""
    
    dim: int  # embedding dimension
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

Built-in implementations:
- `OpenAIEmbedding` — uses OpenAI `text-embedding-3-small`
- `FastEmbedEmbedding` — uses `fastembed` (local, no API key)

### VectorMemory

```python
class VectorMemory(BaseModel):
    """Semantic memory with vector search."""
    
    embedding_fn: EmbeddingFunction
    backend: MemoryBackend  # in-memory dict or SQLite
    
    async def add(self, messages: list[Message]) -> None:
        """Store messages with embeddings."""
    
    async def query(self, text: str, k: int = 5) -> list[Message]:
        """Retrieve semantically similar messages."""
    
    async def clear(self) -> None:
        ...
```

### Memory Manager

```python
class MemoryManager(BaseModel):
    """Coordinates multiple memory systems."""
    
    working: BufferMemory    # recent context (full fidelity)
    episodic: VectorMemory  # past sessions (semantic retrieval)
    semantic: VectorMemory  # knowledge (facts, preferences)
    
    async def get_context(self, query: str) -> str:
        """Build context string from all memory levels."""
    
    async def store(self, messages: list[Message]) -> None:
        """Store across all levels."""
```

---

## Files to create

| File | Description |
|------|-------------|
| `chainforge/memory/embedding.py` | Embedding function protocol + built-in impls |
| `chainforge/memory/vector.py` | Vector memory with semantic search |
| `chainforge/memory/manager.py` | Memory manager |
| `tests/test_memory_vector.py` | Tests |

## Files to modify

| File | Change |
|------|--------|
| `chainforge/memory/__init__.py` | Export new types |
| `chainforge/core/agent.py` | Support VectorMemory in agent context |
