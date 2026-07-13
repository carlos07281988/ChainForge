# 🟡 High Priority Fixes

## 4. `PlanAndExecute` — Fragile JSON Parsing

**File:** `chainforge/agents/plan_execute.py` lines 72-78

**Problem:** Regex-based JSON extraction from LLM output fails on pretty-printed JSON (non-greedy `(.*?)` stops at first `]`), multi-line step descriptions with `]` inside them, or slightly malformed LLM output.

**Fix:** Define a Pydantic model for the plan schema and use `parse_structured_response()` from `chainforge/core/structured_output.py` to parse it robustly.

```python
class PlanStep(BaseModel):
    step: int
    description: str
    tool: str | None = None

class PlanSchema(BaseModel):
    thought: str
    steps: list[PlanStep]
```

## 5. `SelfAsk` — Same Fragile JSON Parsing

**File:** `chainforge/agents/self_ask.py` lines 52-63

**Problem:** Same regex fragility as PlanAndExecute. The sub-question JSON parsing has the same non-greedy match issue.

**Fix:** Define a Pydantic model for sub-questions and use `parse_structured_response()`:

```python
class DecomposeSchema(BaseModel):
    sub_questions: list[str]
```

## 6. `Agent.skills` — Weak Typing

**File:** `chainforge/core/agent.py` line 44

**Problem:** `skills: list[Any]` is too loose. The code uses `hasattr(skill, "to_system_block")` duck-typing, which means a typo in the skill object goes undetected until runtime.

**Fix:** Use `forward reference` or `TYPE_CHECKING` import to type it as `list[Skill]`:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from chainforge.skills.base import Skill

skills: list["Skill"] = Field(default_factory=list)
```

## 7. `Agent._execute_tool` — Args Type Assumption

**File:** `chainforge/core/agent.py` line 99

**Problem:** `tool_obj.run(**tc.args)` assumes `tc.args` is always a dict. But some providers (e.g., when using raw API) might pass string arguments. If `tc.args` is a string, `**tc.args` will raise `TypeError`.

**Fix:** Add a guard in the `ToolCall` construction or in `_execute_tool`:

```python
args = tc.args
if isinstance(args, str):
    try:
        args = json.loads(args)
    except json.JSONDecodeError:
        args = {"_raw": args}
result = await tool_obj.run(**args)
```

## 8. `ConversationalAgent.__init__` — Pydantic Anti-pattern

**File:** `chainforge/agents/conversational.py` line 55

**Problem:** Custom `__init__` is not called when a Pydantic model is deserialized via `model_validate()`. This means `_buffer` and `_summary` won't exist after JSON deserialization.

**Fix:** Replace `def __init__(self, **data)` with `def model_post_init(self, __context)`:

```python
def model_post_init(self, __context):
    self._buffer = BufferMemory(max_messages=self.max_turns_before_summary * 2)
    self._summary = SummaryMemory(max_recent=self.max_turns_before_summary)
```
