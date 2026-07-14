# Cross-Agent Tracing — Distributed Trace Propagation

> 在 A2A 协议调用链中传播分布式追踪上下文

## Motivation

Agent 可能调用其他 Agent（通过 A2A 协议），形成分布式调用链。
需要一种标准化的方式将 trace context 传递给下游，以便：
1. 关联上下游 agent 的日志和事件
2. 分析端到端延迟
3. 定位性能瓶颈

## Design

### W3C Trace Context

使用 W3C Trace Context 标准格式：

```
traceparent: 00-{trace_id}-{span_id}-{trace_flags}
```

- `trace_id`: 32 hex chars — 整个分布式 trace 的唯一 ID
- `span_id`: 16 hex chars — 当前 span 的 ID
- `trace_flags`: 2 hex chars — 采样标记

### Usage

```python
from chainforge.tracing.propagation import (
    TraceContext, inject_headers, extract_headers
)

# Server side (A2A endpoint)
ctx = extract_headers(request.headers)
if ctx is None:
    ctx = TraceContext()  # Start new trace
child = ctx.new_child()

# Client side (A2A call)
ctx = TraceContext()
headers = inject_headers(ctx)
await http_client.post(url, headers=headers)
```

### Integration

| Point | Integration |
|-------|-------------|
| A2A Router | Extract trace context from incoming requests |
| A2A Client | Inject trace context into outgoing requests |
| Middleware | Propagate trace context through agent pipeline |
| Logger | Include trace_id in log records |

### Files

| File | Description |
|------|-------------|
| `chainforge/tracing/propagation.py` | TraceContext, inject/extract helpers |
| `tests/test_tracing_propagation.py` | Tests |
