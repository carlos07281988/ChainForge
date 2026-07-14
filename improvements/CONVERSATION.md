# Conversation Serialization — Save, Load, and Resume Agent Conversations

> 为 ChainForge Agent 提供会话持久化和断点续谈能力

## Design

### Conversation Class

```python
from chainforge.core.conversation import Conversation

conv = Conversation()
async for event in conv.run(agent, "Hello!"):
    if event.type == "text":
        print(event.content)

# Save to file
conv.save("chat.json")

# Load and resume
conv2 = Conversation.load("chat.json")
async for event in conv2.run(agent, "Tell me more"):
    ...
```

### Serialization Format

```json
{
  "version": "1.0",
  "metadata": {"agent_name": "assistant", "session": "abc123"},
  "messages": [
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"}
  ]
}
```

### SummaryMemory Fix

SummaryMemory now auto-summarizes without requiring an LLM call:
- When recent buffer exceeds 2x capacity, old messages are automatically compressed into a summary prefix
- LLM-based compress() still available for higher quality summaries

## Files

| File | Description |
|------|-------------|
| `chainforge/core/conversation.py` | Conversation class |
| `chainforge/memory/summary.py` | Auto-compress fix |
| `tests/test_conversation.py` | Tests |
