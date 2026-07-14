# Code Sandbox + Multi-modal

> 为 ChainForge 添加安全的代码执行沙箱和多模态支持

## Motivation

2025 年的 Agent 框架，代码执行和多模态理解已经是标配能力：
- OpenAI Code Interpreter 让 Agent 能写代码、算数据、出图表
- Claude Computer Use 让 Agent 能操作桌面
- GPT-4o / Gemini 原生支持图像和音频理解

ChainForge 目前只有 text-in/text-out，缺这两块。

---

## Design

### Sandbox Protocol

```python
class Sandbox(Protocol):
    """Isolated execution environment for code."""
    
    async def execute(self, code: str, language: str = "python") -> SandboxResult:
        ...

class SandboxResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_s: float
    files: list[FileContent] = []  # generated files
```

### Implementations

| Implementation | Isolation | Dependencies | Use Case |
|---|---|---|---|
| `SubprocessSandbox` | Process-level | None (stdlib) | Development, testing |
| `DockerSandbox` | Container-level | Docker | Production |

### Sandbox Tools

Built-in tools auto-generated from the sandbox:

```python
@tool
def execute_python(code: str) -> str:
    """Execute Python code in a sandboxed environment."""
    ...

@tool
def execute_bash(command: str) -> str:
    """Execute a shell command in a sandboxed environment."""
    ...
```

---

## Multi-modal

### Extend Message / Part

```python
class Part(BaseModel):
    text: str | None = None
    file: FileContent | None = None  # image, PDF, audio, etc.
    data: dict | None = None
```

### File Loader

```python
class FileLoader:
    """Load and convert files into LLM-compatible formats."""
    
    @staticmethod
    def load_image(path: str) -> Part: ...
    @staticmethod
    def load_pdf(path: str) -> list[Part]: ...
    @staticmethod
    def load_csv(path: str) -> Part: ...
```

### Provider Support

Each provider that supports vision gets automatic image handling:
- OpenAI: GPT-4o vision via `content: [{"type": "image_url", ...}]`
- Anthropic: Claude vision via `content: [{"type": "image", ...}]`
- Google: Gemini vision natively

---

## Files to create

| File | Description |
|------|-------------|
| `chainforge/sandbox/__init__.py` | Exports |
| `chainforge/sandbox/base.py` | Sandbox protocol + result type |
| `chainforge/sandbox/subprocess.py` | Local subprocess sandbox |
| `chainforge/core/files.py` | File loader utilities |
| `tests/test_sandbox.py` | Tests |

## Files to modify

| File | Change |
|------|--------|
| `chainforge/tools/builtin.py` | Add `execute_python`, `execute_bash` tools |
| `chainforge/providers/openai.py` | Support image parts in messages |
| `chainforge/providers/anthropic.py` | Support image parts in messages |
| `chainforge/providers/google.py` | Support image parts in messages |
