# Reasoning Strategies — Composable Thinking Patterns

> 为 ChainForge Agent 添加可组合的推理策略注入框架

## Design

### ReasoningStrategy Protocol

```python
from chainforge.reasoning import ReasoningStrategy

class MyStrategy(ReasoningStrategy):
    async def before_llm(self, messages, context):
        messages.append(Message.system("Think carefully!"))
        return messages, context

agent = Agent(llm=llm, reasoning=[MyStrategy()])
```

### Hook Points

| Hook | When Called | Purpose |
|------|------------|---------|
| `before_llm` | Before each LLM call | Modify messages, inject instructions |
| `after_llm` | After each LLM response | Inspect/self-critique/verify output |
| `on_tool_result` | After tool execution | Process tool results |
| `should_stop` | End of each iteration | Early stopping decisions |

### Built-in Strategies

| Strategy | How It Works |
|----------|-------------|
| `ChainOfThought` | Injects "let me think step by step" prompt |
| `ReasoningSteps` | Asks LLM to plan sub-steps before answering |
| `SelfReflection` | Self-critique after initial response, produces refined answer |
| `Verification` | Double-checks answer before finalizing |

### Files

| File | Description |
|------|-------------|
| `chainforge/reasoning/__init__.py` | Exports |
| `chainforge/reasoning/base.py` | ReasoningStrategy base class |
| `chainforge/reasoning/cot.py` | ChainOfThought, ReasoningSteps |
| `chainforge/reasoning/reflection.py` | SelfReflection, Verification |
| `chainforge/core/agent.py` | Integration with Agent loop |
| `tests/test_reasoning.py` | Tests |
