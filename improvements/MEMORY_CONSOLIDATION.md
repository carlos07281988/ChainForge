# Agent Memory Consolidation

> Phase 22: Simulate human memory consolidation — periodic review, pattern extraction, pruning.
> Status: 🛠 Implementing | Priority: P1 | Effort: 8-10 days

---

## Architecture

```
Memory Store (working memory)
    │
    ▼
┌──────────────────────────────────────────────┐
│         MemoryConsolidator                    │
│                                              │
│  1. Review & Score                           │
│     - recency: how recent?                   │
│     - frequency: how often accessed?         │
│     - consistency: matches other memories?   │
│     → Confidence score [0.0, 1.0]           │
│                                              │
│  2. Prune                                    │
│     - Remove memories below threshold        │
│                                              │
│  3. Compress                                 │
│     - Group related memories                 │
│     - Merge into summaries                   │
│                                              │
│  4. Report                                   │
│     - reviewed, pruned, compressed counts    │
│     - identified patterns                    │
└──────────────────────────────────────────────┘
    │
    ▼
Memory Store (consolidated)
```

## API Design

```python
from chainforge.core.consolidation import MemoryConsolidator, ConsolidationConfig

# Standalone usage
consolidator = MemoryConsolidator(
    config=ConsolidationConfig(
        confidence_threshold=0.3,
        max_memories=500,
        enable_compression=True,
    )
)

memories = [
    "User likes Python",
    "User works at Google",
    "User prefers dark mode",
    "User is a software engineer",
    "User uses VS Code",
]

# Review and consolidate
report = consolidator.consolidate(memories)
# {'reviewed': 5, 'pruned': 0, 'compressed': 2, 'remaining': 3, 'patterns': [...]}

# With AutoMemoryManager integration
memory = AutoMemoryManager(llm=llm)
consolidator = MemoryConsolidator(config=config)
report = await consolidator.consolidate_manager(memory)
# Uses memory's internal store, prunes & compresses automatically
```

## ConsolidationConfig

| Field | Default | Description |
|-------|---------|-------------|
| confidence_threshold | 0.3 | Prune memories below this score |
| max_memories | 500 | Max memories before triggering consolidation |
| enable_compression | True | Merge related memories into summaries |
| llm_assisted | False | Use LLM for compression and pattern extraction |
