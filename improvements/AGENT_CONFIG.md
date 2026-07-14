# Agent Config Declaration

> 为 ChainForge 添加声明式 Agent 配置文件支持

## Motivation

目前创建 Agent 全部用 Python 代码：

```python
agent = Agent(
    llm=OpenAIProvider(model="gpt-4o"),
    tools=[search, calculate],
    system_prompt="You are helpful.",
    temperature=0.3,
)
```

但更成熟的使用方式是声明式配置（YAML/JSON）：

```yaml
name: research-assistant
llm:
  provider: openai
  model: gpt-4o
  temperature: 0.3
tools:
  - name: web_search
    type: builtin
  - name: calculator
    type: builtin
memory:
  type: vector
  backend: sqlite
system_prompt: "You are a research assistant."
```

好处：
- 非 Python 用户也能定义 Agent
- 配置可版本管理、可 review
- 支持环境变量注入（API Key 等敏感信息不硬编码）
- 可组合模板

---

## Design

### Config Schema

```python
class LLMConfig(BaseModel):
    provider: str  # "openai" | "anthropic" | "google" | "azure" | "bedrock"
    model: str = "gpt-4o"
    temperature: float | None = None
    max_tokens: int | None = None
    api_key: str | None = None  # supports ${ENV_VAR} syntax

class ToolConfig(BaseModel):
    name: str
    type: str  # "builtin" | "mcp" | "skill"
    config: dict = {}

class MemoryConfig(BaseModel):
    type: str = "buffer"  # "buffer" | "summary" | "vector"
    backend: str = "memory"  # "memory" | "sqlite"
    config: dict = {}

class AgentConfig(BaseModel):
    name: str = "agent"
    llm: LLMConfig
    tools: list[ToolConfig] = []
    memory: MemoryConfig | None = None
    skills: list[str] = []
    system_prompt: str | None = None
    max_iterations: int = 10
    temperature: float | None = None
```

### Loader & Builder

```python
def load_agent_config(path: str) -> AgentConfig:
    """Load config from YAML or JSON file."""
    ...

def build_agent_from_config(config: AgentConfig) -> Agent:
    """Build a ChainForge Agent from config."""
    ...
```

### CLI Integration

```bash
chainforge init --from-config agent.yaml
chainforge serve --config agent.yaml
```

### Template System

```bash
chainforge init my-project --template search-agent
```

---

## Files to create

| File | Description |
|------|-------------|
| `chainforge/config/__init__.py` | Exports |
| `chainforge/config/schema.py` | Pydantic config models |
| `chainforge/config/loader.py` | YAML/JSON loader + env var injection |
| `chainforge/config/builder.py` | Build Agent from config |
| `tests/test_config.py` | Tests |

## Files to modify

| File | Change |
|------|--------|
| `chainforge/cli/__init__.py` | Add `--config` flag to `serve`, `init` commands |
