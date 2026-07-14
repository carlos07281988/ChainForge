# Prompt Templates — Variable Injection, Composition, Chat Templates

> 为 ChainForge 提供像 LangChain 一样灵活的提示词模板系统

## Design

### PromptTemplate

```python
from chainforge.prompts import PromptTemplate

tmpl = PromptTemplate("Hello, {name}! Today is {day}.")
result = tmpl.format(name="Alice", day="Monday")
# "Hello, Alice! Today is Monday."
```

### ChatPromptTemplate

```python
from chainforge.prompts import ChatPromptTemplate

tmpl = ChatPromptTemplate.from_messages([
    ("system", "You are a {role} expert."),
    ("user", "Tell me about {topic}"),
])
messages = tmpl.format_messages(role="Python", topic="async")
```

### FewShotPromptTemplate

```python
from chainforge.prompts import FewShotPromptTemplate

tmpl = FewShotPromptTemplate(
    examples=[{"q": "2+2", "a": "4"}],
    example_prompt=PromptTemplate("Q: {q}\nA: {a}"),
    prefix="Answer these:",
    suffix="Q: {input}\nA:",
)
```

## Files

| File | Description |
|------|-------------|
| `chainforge/prompts/__init__.py` | Exports |
| `chainforge/prompts/template.py` | PromptTemplate, FewShotPromptTemplate |
| `chainforge/prompts/chat.py` | ChatPromptTemplate, MessagePlaceholder |
| `tests/test_prompts.py` | Tests |
