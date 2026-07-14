# Agent Testing Suite — Mock LLM, Simulation, Regression

> 为 ChainForge Agent 提供无需真实 API 调用的测试能力

## Motivation

测试 Agent 最大的痛点：
1. 每次测试都要调用真实 LLM API → 慢、贵、不可重复
2. Agent 行为依赖 LLM 输出 → 难以断言
3. 边界条件（超时、错误、工具调用）难以覆盖

## Design

### MockLLM

```python
from chainforge.testing import MockLLM, mock_text_response, mock_tool_call_response

llm = MockLLM(responses=[
    mock_text_response("Hello!"),
    mock_tool_call_response("calculate", {"x": 1}),
    mock_text_response("Result: 1"),
])

# Track calls
llm.assert_called(times=3)
llm.assert_last_prompt_contains("calculate")
```

### mock_agent() Helper

```python
from chainforge.testing import mock_agent

agent, llm = mock_agent(
    responses=["Hello!", "Result: 42"],
    tools=[my_tool],
    system_prompt="You are helpful.",
)
```

### Assertions

| Method | Purpose |
|--------|---------|
| `assert_called(times)` | Verify call count |
| `assert_last_prompt_contains(text)` | Verify prompt content |
| `reset()` | Reset state between tests |

## Files

| File | Description |
|------|-------------|
| `chainforge/testing/__init__.py` | Exports |
| `chainforge/testing/mock_llm.py` | MockLLM, MockResponse, mock_agent |
| `tests/test_testing.py` | Tests |
