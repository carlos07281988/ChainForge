# Context Management — Window Control, Compression, Budget

> 管理 Agent 上下文窗口，优化 token 使用效率

## Motivation

LLM 上下文窗口再大也是有限的（128K-2M tokens），而且：
1. 长上下文降低响应速度、增加成本
2. 关键信息可能被淹没在海量历史中
3. 不同消息类型（system prompt、工具结果、对话历史）应该有不同的优先级和预算

## Design

### Three Strategies

| Strategy | How | When |
|----------|-----|------|
| `SlidingWindowStrategy` | Drop oldest conversation messages | Default, no LLM call needed |
| `CompressorStrategy` | Summarize old messages via LLM | Long-running conversations |
| `SelectiveStrategy` | Keep semantically relevant history | *(planned)* |

### Token Budget

```
┌─────────────────────────────────────────────┐
│  max_total (128K)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │  system  │ │conversation│ │ tool results │ │
│  │  (4K)    │ │  (100K)   │ │   (20K)      │ │
│  └──────────┘ └──────────┘ └──────────────┘ │
│  reserve_for_response (4K)                   │
└─────────────────────────────────────────────┘
```

### Files

| File | Description |
|------|-------------|
| `chainforge/context/base.py` | ContextManager protocol, TokenBudget, token estimation |
| `chainforge/context/sliding_window.py` | SlidingWindowStrategy |
| `chainforge/context/compressor.py` | CompressorStrategy |
| `tests/test_context.py` | Tests |
