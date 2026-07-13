# 🔵 Medium Priority Improvements

## 9. `RateLimitMiddleware` — Shared State Semantics

**File:** `chainforge/middleware/rate_limit.py` lines 31-33

**Problem:** `tokens` and `last_refill` are closure variables, meaning if the same middleware function is shared across multiple agents or concurrent calls, the rate limit is applied globally. This might be desired (rate limit across all agents) or might not (rate limit per agent). The behavior is undocumented.

**Fix:** Add a `per_instance: bool = False` parameter. When True, create a `TokenBucket` object per call. When False (default), use shared closure state. Document clearly.

## 10. `HumanInTheLoop.middleware()` — Fragile Event Interception

**File:** `chainforge/core/human_in_loop.py` lines 104-147

**Problem:** HITL middleware intercepts `EventType.tool_call` events in the event stream and blocks for human input. But if another middleware (e.g., tracing) is placed AFTER HITL in the chain, it will see the rejected tool call as a normal tool_call event without context of the rejection.

**Fix:** Add a dedicated approval event type to the stream protocol:

```python
class EventType(str, Enum):
    ...
    approval_needed = "approval_needed"  # new
```

The HITL middleware emits this BEFORE the tool call, and the agent loop checks for approval state before executing. Or alternatively, document the ordering requirement clearly.

## 11. `GoogleProvider._get_client()` — Global State

**File:** `chainforge/providers/google.py` line 41

**Problem:** `genai.configure(api_key=api_key)` sets module-level global state in the google-generativeai SDK. If two GoogleProvider instances with different API keys exist, the second one overwrites the first's configuration.

**Fix:** At minimum, add a warning comment. Ideally, investigate if the SDK supports per-request API key configuration. If not, document that only one GoogleProvider instance should exist per process.

## 12. Scattered `import asyncio` in Function Bodies

**Files:**
- `chainforge/core/tool.py:98` (`FunctionTool.__call__`)
- `chainforge/core/pipeline.py:77` (`Pipeline.__call__`)
- `chainforge/mcp/client.py:45` (`MCPTool.__call__`)
- `chainforge/skills/base.py:107` (`SkillTool.__call__`)
- `chainforge/agents/agent_tool.py:80` (`AgentTool.__call__`)
- `chainforge/agents/agent_chain.py:156` (`ChainTool.__call__`)

**Problem:** Inconsistent — `import asyncio` is repeated in ~6 places inside function bodies. These are all for the same pattern: wrapping `async def run()` with `asyncio.run()` for sync convenience.

**Fix:** Create a utility function in `chainforge/core/utils.py`:

```python
def run_sync(coro):
    import asyncio
    return asyncio.run(coro)
```

And replace all scattered import sites with it. Or use a shared base class/mixin for sync-wrapping.
