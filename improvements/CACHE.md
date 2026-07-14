# LLM Cache — Response Caching with TTL and Middleware

> 为 ChainForge Agent 添加 LLM 响应缓存，减少 API 调用

## Design

### Cache Interface

```python
from chainforge.cache import BaseCache, InMemoryCache

cache = InMemoryCache(ttl=3600)  # 1 hour
await cache.set("key", "response")
result = await cache.get("key")
```

### Middleware Integration

```python
from chainforge.cache import CacheMiddleware

agent = Agent(
    llm=llm,
    middlewares=[CacheMiddleware(cache=InMemoryCache(ttl=300))],
)
```

### Cache Key

Cache key is based on `(model, messages_hash, tools_hash)`.

## Files

| File | Description |
|------|-------------|
| `chainforge/cache/__init__.py` | Exports |
| `chainforge/cache/base.py` | BaseCache protocol, CacheEntry |
| `chainforge/cache/memory.py` | InMemoryCache |
| `chainforge/cache/middleware.py` | CacheMiddleware |
| `tests/test_cache.py` | Tests |
