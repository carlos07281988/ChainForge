# 🔴 Critical Fixes

## 1. `eval()` in `calculate` tool — Security Risk

**File:** `chainforge/tools/builtin.py` line 21

**Problem:** The `calculate` tool uses `eval()` with empty `__builtins__`, but this is still exploitable (e.g., `(1).__class__.__bases__[0].__subclasses__()` can escape).

**Fix:** Replace `eval()` with a safe math expression parser using `ast.parse` and a node visitor that only allows safe operations (numbers, basic arithmetic operators, and math functions).

## 2. Bedrock Streaming Tool Call Input Accumulation

**File:** `chainforge/providers/bedrock.py` lines 200-202

**Problem:** The `tool_use_delta` case reads the input into a local variable `tc_input` but never accumulates it into `tool_call_deltas[idx]["input"]`. This means streaming tool calls via Bedrock will always have empty input arguments.

```python
elif delta.get("type") == "tool_use_delta":
    tc_input = delta.get("input", "")
    # Accumulate tool call input  ← NO CODE HERE
```

**Fix:** Accumulate the input delta character-by-character into `tool_call_deltas[idx]["input"]`. Also handle the initial `content_block_start` to extract the tool name/id correctly, and parse the accumulated JSON at `message_stop`.

## 3. `SummaryMemory` — Never Summarizes

**File:** `chainforge/memory/summary.py`

**Problem:** The docstring says "compresses conversation history into a running summary" but `save()` only appends to `recent_messages` and trims. The actual summarize logic lives in `ConversationalAgent.run()` (lines 111-118), making `SummaryMemory` misleading as a standalone component.

**Fix:** Either:
- Option A: Add a `compress()` method to `SummaryMemory` that takes an LLM and does the summarize internally.
- Option B: Rename to `RollingMemory` and update docstring to reflect it's a rolling window without intelligent summarization.
- Recommendation: Option A — add `async compress(llm)` method.
