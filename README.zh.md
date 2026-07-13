<div align="center">

```
        ________  __________   _____  _   ___________   _____  ___________
       / ____/ / / / ____/ /  / __ \/ | / / ____/   | / __ \/ ____/ ___/
      / /   / /_/ / /_  / /  / / / /  |/ / / __/ /| |/ / / / / __/ __ \
     / /___/ __  / __/ / /___/ /_/ / /|  / /_/ / ___ / /_/ / /_/ / /_/ /
     \____/_/ /_/_/   /_____/\____/_/ |_/\____/_/  |_\____/\____/_____/

```

</div>

# ChainForge — 锻造链

**把你的 LLM 调用链、工具链、处理链"锻造"出来。**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-green)]()
[![Tests](https://img.shields.io/badge/tests-201%20passed-brightgreen)]()
[![Dependencies](https://img.shields.io/badge/dependencies-2-red)]()

> **ChainForge 是 LangChain 如果今天重新设计应有的样子。**  
> 极简 · 流式优先 · 类型安全 · 异步原生 · 零开销抽象

---

## 📖 目录

- [为什么选择 ChainForge](#-为什么选择-chainforge)
- [快速开始](#-快速开始)
- [安装](#-安装)
- [核心概念](#-核心概念)
- [示例](#-示例)
- [架构](#-架构)
- [API 参考](#-api-参考)
- [设计原则](#-设计原则)
- [代理模式](#-代理模式-10-种)
- [代理链接](#-代理链接)
- [日志](#-日志)
- [技能系统](#-技能系统)
- [评估测试](#-评估测试)
- [控制台](#-控制台)
- [DAG 可视化编辑器](#-dag-可视化编辑器)
- [路线图](#-路线图)

---

## 🎯 为什么选择 ChainForge

LangChain 开创了 Agent 框架的先河，但其架构背负着多年的兼容性包袱。ChainForge 是一次彻底的重构：

| 痛点 | LangChain | ChainForge | 对比 |
|---|---|---|---|
| API 复杂度 | Chain, Runnable, LCEL 多重抽象 | **Protocol 接口** — 最小化 API | 降低 80% 学习成本 |
| 流式 | 事后追加, 需要 Callback | **Streaming-first** — `Stream` 默认 | 原生支持 |
| 工具调用 | 层层封装的 Pipeline | **Tool Protocol** — 一等公民 | 即插即用 |
| 状态管理 | 独立 LangGraph 框架 | **Agent 内置循环**, Pipeline `>>` 组合 | 无需额外框架 |
| 可观测性 | LangSmith 外部服务 | **内建 Middleware** — ConsoleTracer 三行代码 | 零外部依赖 |
| 异步 | 支持但非默认 | **Async-native** — sync 是薄封装 | 性能更优 |
| 错误处理 | 堆栈深, 不易追踪 | **类型化错误** (ProviderError, ToolExecutionError) | 精确定位 |
| 依赖 | 100+ 间接依赖 | **核心仅 pydantic + stdlib** | 极致轻量 |

---

## 🚀 快速开始

```bash
pip install chainforge
```

```python
import asyncio
from chainforge import Agent, tool
from chainforge.providers import OpenAIProvider


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """获取城市天气"""
    temps = {"beijing": 28, "tokyo": 22, "london": 15}
    return f"{city.title()}: {temps.get(city.lower(), 20)}°C"


async def main():
    agent = Agent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[get_weather],
        system_prompt="你是一个天气助手。",
    )
    stream = await agent.run("北京和东京的天气怎么样？")
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)
        elif event.type == "tool_call":
            print(f"\n🔧 调用 {event.data['name']}({event.data['args']})")

asyncio.run(main())
```

---

## 📦 安装

```bash
pip install chainforge                          # 核心（仅 pydantic）
pip install "chainforge[openai]"                # OpenAI 支持
pip install "chainforge[anthropic]"             # Anthropic 支持
pip install "chainforge[google]"                # Google Gemini 支持
pip install "chainforge[server]"                # HTTP API 服务
pip install "chainforge[all]"                   # 全部功能
```

需要 Python 3.11+。

---
## 📚 核心概念

ChainForge 的核心概念围绕 **Protocol 接口** 设计，最小化学习成本。

### Agent（代理）

Agent 是 ChainForge 的核心抽象 — 一个拥有 LLM 和工具的自主循环：

```python
agent = Agent(llm=OpenAIProvider(), tools=[get_weather])
stream = await agent.run("北京天气怎么样？")
```

工作流程：`LLM → 工具调用（可选）→ LLM → ... → 最终输出`

### Stream（流）

所有 Agent 运行都返回 `Stream` — 一个事件驱动的异步迭代器：

```python
async for event in stream:
    if event.type == "text":
        print(event.content, end="")
    elif event.type == "tool_call":
        print(f"🔧 {event.data['name']}")
    elif event.type == "state":
        print(f"状态: {event.data['state']}")
```

**事件类型：** `text`, `tool_call`, `tool_result`, `state`, `status`, `error`, `done`

### Tool（工具）

通过 `@tool` 装饰器将任意函数变为 Agent 可调用的工具：

```python
@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return f"{city}: 25°C"
```

工具自动从函数签名生成 JSON Schema，支持类型注解和文档字符串。

### Middleware（中间件）

中间件是处理 Agent 运行的钩子链 — 用于日志、追踪、限流、重试等横切关注点：

```python
agent = Agent(llm=llm, tools=[...], middlewares=[
    retry_middleware(max_retries=3),
    rate_limit_middleware(max_per_minute=60),
    logging_middleware(),
])
```

### Pipeline（流水线）

将多个步骤通过 `>>` 操作符组合为处理管道：

```python
pipeline = step1 >> step2 >> step3
stream = pipeline.run(input_data)
```

支持 DAG（有向无环图）执行，可实现分支、合并、条件路由。

---

## 💡 示例

### 基础 Agent

```python
import asyncio
from chainforge import Agent, tool
from chainforge.providers import OpenAIProvider

@tool
def get_time(timezone: str = "UTC") -> str:
    """获取指定时区的当前时间"""
    import datetime
    return f"{timezone}: {datetime.datetime.now().isoformat()}"

async def main():
    agent = Agent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[get_time],
        system_prompt="你是一个实用助手。",
    )
    stream = await agent.run("现在纽约几点了？")
    async for event in stream:
        if event.type == "text":
            print(event.content, end="", flush=True)

asyncio.run(main())
```

### 带中间件的 Agent

```python
from chainforge.middleware.logging_mw import logging_middleware
from chainforge.middleware.retry import retry_middleware

agent = Agent(
    llm=llm,
    tools=[search, calculate],
    middlewares=[
        retry_middleware(max_retries=3),
        logging_middleware(log_input=True),
    ],
)
```

### 结构化输出

```python
from pydantic import BaseModel

class Movie(BaseModel):
    title: str
    year: int
    rating: float

stream = await agent.run(
    "推荐三部科幻电影",
    response_model=Movie,
)
movies = await stream.collect_structured()  # -> list[Movie]
```

### 多 Agent 编排

```python
from chainforge.orchestration.swarm import Swarm
from chainforge.orchestration.supervisor import Supervisor

# Swarm：多个 Agent 并发执行
swarm = Swarm(agents=[researcher, writer, editor])
result = await swarm.run("写一篇 AI 文章")

# Supervisor：一个 Agent 协调其他 Agent
supervisor = Supervisor(
    supervisor_agent=coordinator,
    workers=[researcher, writer],
)
result = await supervisor.run("调研并写报告")
```

---


## 🏗 架构

```
chainforge/
│
├── core/                 # 核心基元
│   ├── agent.py          # Agent 执行循环 (LLM ↔ Tools ↔ LLM...)
│   ├── llm.py            # LLM 协议 + LLMResponse
│   ├── tool.py           # Tool 协议 + FunctionTool + @tool 装饰器
│   ├── message.py        # Message, ToolCall, ToolResult, Role 枚举
│   ├── stream.py         # StreamEvent (7 种类型) + Stream 包装器
│   ├── pipeline.py       # 线性步骤组合 (>>)
│   ├── graph.py          # DAG 图执行引擎
│   ├── middleware.py     # 中间件链 — 可组合的 Agent 钩子
│   ├── state.py          # Agent 状态机 (StateTracker)
│   ├── structured_output.py  # Pydantic response_model 解析
│   ├── human_in_loop.py  # 人为审批/中断钩子
│   ├── utils.py          # 核心工具 (run_sync)
│   └── errors.py         # 类型化错误 (ProviderError, ToolExecutionError, ...)
│
├── providers/            # LLM 实现
│   ├── openai.py         # OpenAI — 流式、工具调用、Token 统计
│   ├── anthropic.py      # Anthropic — 流式、工具调用、Token 统计
│   ├── google.py         # Google Gemini — 流式、工具调用
│   ├── azure.py          # Azure OpenAI — 流式、工具调用
│   └── bedrock.py        # AWS Bedrock — Claude, Llama, Mistral, Titan
│
├── agents/               # 10 种 Agent 模式
│   ├── react.py          # ReAct (思考/行动/观察循环)
│   ├── plan_execute.py   # 规划 → 执行 → 综合
│   ├── reflection.py     # 生成 → 反思 → 改进
│   ├── self_ask.py       # 分解 → 回答 → 综合
│   ├── tree_of_thoughts.py  # BFS 多路径推理
│   ├── chain_of_thought.py  # 思维链 + 自一致性
│   ├── conversational.py # 多轮对话 + 自动摘要压缩
│   ├── router.py         # 意图分类 → 路由到专家
│   ├── tool_agent.py     # 重型工具编排 Agent
│   ├── agent_chain.py    # 顺序 Agent 组合
│   ├── agent_tool.py     # Agent 包装为可调用 Tool
│   └── agent_hub.py      # 中央注册 + 发现 + 自动路由
│
├── tools/                # 工具系统
│   └── builtin.py        # 内置工具 (current_time, calculate, echo)
│
├── skills/               # 可复用技能包
│   ├── base.py           # Skill 模型 + SkillTool 包装器
│   ├── loader.py         # SKILL.md 文件加载器
│   └── registry.py       # SkillRegistry — 注册、搜索、发现
│
├── memory/               # 对话记忆
│   ├── buffer.py         # 滑动窗口缓冲区
│   └── summary.py        # 运行摘要压缩
│
├── middleware/            # 中间件实现
│   ├── logging_mw.py     # 结构化日志中间件
│   ├── retry.py          # 指数退避重试
│   ├── timeout.py        # 执行超时保护
│   ├── rate_limit.py     # 令牌桶限流器
│   ├── opentelemetry.py  # OpenTelemetry 追踪中间件
│   └── langfuse.py       # Langfuse 可观测性中间件
│
├── orchestration/        # 多 Agent 编排
│   ├── supervisor.py     # 规划 → 委派 → 综合
│   └── swarm.py          # 并行 / 顺序 / 会议模式
│
├── eval/                 # 评估与测试框架
│   ├── case.py           # EvalCase — 测试提示 + 预期行为
│   ├── metrics.py        # MetricsCollector — 时间、Token、成本、成功率
│   ├── suite.py          # EvalSuite — 集合 + JSON 加载/保存
│   ├── runner.py         # EvalRunner — 对 Agent 执行测试套件
│   └── report.py         # EvalReport — JSON / Markdown / HTML / Text
│
├── tracing/              # 可观测性
│   └── tracer.py         # Tracer, Span, ConsoleTracer, tracing_middleware
│
├── mcp/                  # Model Context Protocol
│   └── client.py         # MCPClient — 动态工具发现 (stdio/SSE)
│
├── cli/                  # CLI 接口
│   └── __init__.py       # init, quickstart, skill, serve, run, eval
│
├── server.py             # HTTP 服务 (FastAPI + REST + SSE)
├── logging.py            # 结构化日志 (text/json, 模块级日志级别)
│
├── examples/             # 可运行示例
│   ├── basic_agent.py    # 天气 + 搜索 Agent 演示
│   └── memory_example.py # 多轮对话 + 记忆
│
└── tests/                # 210+ 测试
```

### 执行流程

```
用户输入 → Agent.run() → LLM.generate() → 有工具调用？
    ↓                        ↓
  是 → 执行工具 → 追加结果 → LLM.generate() → ...
    ↓
  否 → 输出文本 → 完成
```

## 📖 API 参考

### Agent

```python
agent = Agent(
    llm: LLM,                              # LLM 提供者
    tools: list[Tool] = [],                # 可用工具
    skills: list[Skill] = [],              # 技能（SKILL.md）
    system_prompt: str | None = None,      # 系统提示
    max_iterations: int = 10,              # 最大迭代次数
    max_tokens: int | None = None,         # 最大 Token 数
    temperature: float | None = None,      # LLM 温度参数
    middlewares: list | None = None,       # 中间件链
    parallel_tool_calls: bool = True,      # 并行工具执行
)
```

**方法：**
- `run(prompt, *, context, response_model) -> Stream` — 执行 Agent
- `_all_tools() -> list[Tool]` — 获取所有可用工具

### Stream

```python
stream = await agent.run("Hello")
async for event in stream:
    ...
await stream.collect_text()                # 收集所有文本
events = await stream.collect()             # 收集所有事件
structured = await stream.collect_structured(model)  # 结构化输出
states = await stream.collect_states()      # 收集状态转换
```

### Tool

```python
@tool
def my_tool(param1: str, param2: int = 42) -> str:
    """工具描述。"""
    return f"结果: {param1}"
```

### Pipeline

```python
pipeline = step1 >> step2 >> step3
stream = pipeline.run(input_data)
```

### DAG（有向无环图）

```python
dag = DAG(name="process")
dag.add_node("double", fn=lambda x: x * 2)
dag.add_node("add_one", fn=lambda x: x + 1)
dag.add_edge("double", "add_one")
stream = dag.run(21)
```

---

## 🎨 设计原则

1. **Protocol-based（协议优先）** — 基于 Protocol 接口而非继承。任何实现了所需接口的对象都是 `LLM` 或 `Tool`。
2. **Streaming-first（流式优先）** — Agent 运行返回 `Stream`，而非等待完整结果。流式是默认行为。
3. **Async-native（异步原生）** — 异步是首要方式，但 `Pipeline.__call__()` 和 `Tool.__call__()` 也支持同步调用。
4. **Type-safe（类型安全）** — 全 Pydantic 模型，深入的类型推导，IDE 补全友好。
5. **Zero-overhead abstractions（零开销抽象）** — 核心仅 2 个依赖（pydantic + typing_extensions）。MCP、Server 等为可选安装。
6. **Six principles**

---

```

---

## 🤖 代理模式（10 种）

ChainForge 内置 10 种 Agent 模式，覆盖不同场景：

| # | 模式 | 文件 | 适用场景 | 核心流程 |
|---|---|---|---|---|
| 1 | **Agent** 基础代理 | core/agent.py | 通用任务 | LLM → 工具 → LLM |
| 2 | **ReActAgent** 反应代理 | agents/react.py | 推理任务 | Thought → Action → Observation |
| 3 | **PlanAndExecute** 规划执行 | agents/plan_execute.py | 复杂多步骤 | 规划 → 执行 → 综合 |
| 4 | **Reflection** 反思代理 | agents/reflection.py | 质量优先 | 生成 → 批评 → 改进(×N) |
| 5 | **SelfAsk** 自问代理 | agents/self_ask.py | 研究分析 | 分解 → 回答 → 综合 |
| 6 | **TreeOfThoughts** 思维树 | agents/tree_of_thoughts.py | 复杂推理 | BFS 多路径 + 评分 |
| 7 | **ChainOfThought** 思维链 | agents/chain_of_thought.py | 高可靠性推理 | N 路推理 + 投票 |
| 8 | **ConversationalAgent** 对话代理 | agents/conversational.py | 多轮对话 | 自动上下文管理 |
| 9 | **RouterAgent** 路由代理 | agents/router.py | 多技能系统 | 意图分类 + 路由 |
| 10 | **ToolAgent** 工具代理 | agents/tool_agent.py | 多工具编排 | 自动工具调度 |

### 快速选择指南

| 你需要 | 推荐模式 | 理由 |
|---|---|---|
| "用工具回答一个问题" | **Agent** | 简单、快速 |
| "请逐步推理" | **ReActAgent** | 显式思考过程 |
| "调研并写一份报告" | **PlanAndExecute** | 结构化多步骤 |
| "审查并改进这段代码" | **Reflection** | 自我批评循环 |
| "比较两种技术" | **SelfAsk** | 分而治之 |
| "解一道逻辑题" | **TreeOfThoughts** | 多路径探索 |
| "可靠地验证一个事实" | **ChainOfThought** | 自洽性投票 |
| "进行长时间对话" | **ConversationalAgent** | 自动上下文管理 |
| "构建多技能助手" | **RouterAgent** | 意图路由 |
| "自动化数据管道" | **ToolAgent** | 工具编排 |

---

## 🔗 代理链接

三种方式连接和组合 Agent：

### AgentTool — Agent 即工具

将任意 Agent 包装为 Tool，供其他 Agent 调用：

```python
from chainforge.agents import AgentTool

search_tool = AgentTool(search_agent, name="web_search", description="搜索信息")
main_agent = Agent(llm=llm, tools=[search_tool, calc_tool])
```

### AgentChain — 顺序组合

Agent 版 Pipeline，上一个 Agent 的输出传递给下一个：

```python
from chainforge.agents import AgentChain

chain = AgentChain(name="pipeline")
chain.add_step("research", researcher)
chain.add_step("write", writer)
stream = await chain.run("调研 AI 芯片市场")
```

### AgentHub — 注册中心

管理、发现、自动路由 Agent：

```python
from chainforge.agents import AgentHub

hub = AgentHub()
hub.register("search", agent, "搜索", tags=["public"])
router = hub.create_router(classifier_llm=llm)
chain = hub.create_chain(["search", "analyze"])
```

---

## 📋 日志系统

```python
from chainforge import configure_logging

configure_logging(level="INFO")                   # 文本格式
configure_logging(level="DEBUG", format="json")   # JSON 结构化
configure_logging(level="WARNING", output="logs/run.log")  # 文件输出
```

日志中间件自动捕获 Agent 运行全生命周期：

```python
from chainforge.middleware.logging_mw import logging_middleware

agent = Agent(llm=llm, tools=[...], middlewares=[logging_middleware()])
```

输出 JSON 格式：

```json
{"ts": "14:30:01.234", "level": "INFO", "logger": "chainforge.agent", "data": {"tool_call": {"name": "get_weather"}}}
```

---

## 🛠 技能系统

加载 Codex 格式的技能（SKILL.md）：

```python
from chainforge.skills import Skill, SkillRegistry

skill = Skill.load("./skills/my-skill/SKILL.md")
agent = Agent(llm=llm, skills=[skill])

registry = SkillRegistry()
registry.load_dir("./skills")
tools = registry.to_tools()
```

---

## 🧪 评估测试

ChainForge 内置评估框架，用于对 Agent 进行基准测试和性能评估。

### 快速开始

```python
from chainforge.eval import EvalCase, EvalSuite, EvalRunner, format_report

cases = [
    EvalCase(name="greeting", prompt="Say hello!",
             expected_contains=["hello"], tags=["basic"]),
    EvalCase(name="tool_use", prompt="Weather in Beijing?",
             expected_tool="get_weather", tags=["tools"]),
]
suite = EvalSuite(name="demo", cases=cases)
runner = EvalRunner(agent, suite, name="my_agent")
result = await runner.run_all()
print(format_report(result, fmt="text"))
```

### CLI 命令

```bash
# 对已注册的 Agent 运行评估
chainforge eval my_agent

# 运行特定测试用例
chainforge eval my_agent --cases greeting

# 从 JSON 文件加载测试套件
chainforge eval my_agent --suite test_suite.json

# 导出为 HTML 报告
chainforge eval my_agent --format html --output report.html
```

### 测试用例配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 唯一名称 |
| `prompt` | `str` | 输入提示 |
| `expected` | `list[ExpectedBehavior]` | 预期行为 |
| `expected_contains` | `list[str]` | 输出应包含的字符串 |
| `expected_tool` | `str` | 应调用的工具 |
| `tags` | `list[str]` | 标签 |
| `weight` | `float` | 评分权重 |

### 报告格式

```python
text_report = format_report(result, fmt="text")      # 纯文本
md_report = format_report(result, fmt="markdown")    # Markdown
html_report = format_report(result, fmt="html")      # HTML
json_report = format_report(result, fmt="json")      # JSON
```

### HTTP API

```bash
curl -X POST http://localhost:8000/api/v1/eval/run \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my_agent", "cases": [{"name": "t1", "prompt": "Hi"}]}'
```

---

## 🖥 控制台

ChainForge 提供 Web 控制台，支持实时 Agent 流式可视化和 DAG 编辑。

### 启动

```bash
pip install "chainforge[server]"
chainforge serve --port 8000
# 打开浏览器访问 http://localhost:8000/dashboard
```

### 页面

| 页面 | URL | 功能 |
|------|-----|------|
| **总览** | `/dashboard` | 注册的 Agent 列表、服务器状态 |
| **Agent 运行** | `/dashboard/agent-run` | 实时流式可视化，状态机跟踪 |
| **DAG 编辑器** | `/dashboard/dag-editor` | 交互式流水线编辑器 |

### 实时流式可视化

Agent 运行页面展示：
- **状态机** — 实时高亮当前 Agent 状态（初始化 → 思考 → 执行工具 → 观察 → 响应 → 完成）
- **事件流** — 滚动日志，包含时间戳、事件类型和内容
- **指标** — 响应时间、工具调用次数、迭代次数

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/agents` | 列出所有 Agent |
| GET | `/api/v1/agents/{id}` | Agent 详情 |
| POST | `/api/v1/agents/{id}/run` | 运行 Agent (JSON) |
| GET | `/api/v1/agents/{id}/run/stream` | 运行 Agent (SSE 流) |
| POST | `/api/v1/eval/run` | 评估测试 |
| GET | `/api/v1/dag/stream` | 执行 DAG (SSE 流) |
| GET | `/api/v1/health` | 健康检查 |

---

## 🔧 DAG 可视化编辑器

DAG（有向无环图）编辑器可视化构建和执行 Agent 流水线。

### 功能

- **拖拽** — 自由移动节点
- **可视连接** — 点击输出端口 → 输入端口创建连线
- **节点类型** — Step、Input、Output、Router、Merge
- **JSON 导出** — 导出 DAG 为 JSON 复用
- **实时执行** — 运行 DAG 并通过 SSE 查看结果

### 节点类型

| 类型 | 用途 | 说明 |
|------|------|------|
| **Input** | 入口节点 | 接收初始数据 |
| **Step** | 处理步骤 | 执行函数转换 |
| **Router** | 条件路由 | 基于值分支 |
| **Merge** | 合并节点 | 组合多个输入 |
| **Output** | 输出节点 | 返回最终结果 |

### 编程式 DAG

```python
from chainforge import DAG

dag = DAG(name="pipeline")
dag.add_node("double", fn=lambda x: x * 2)
dag.add_node("add_one", fn=lambda x: x + 1)
dag.add_edge("double", "add_one")

stream = dag.run(21)
async for event in stream:
    if event.type == "text":
        print(event.content)  # 42
```

---


## 🗺 路线图

已完成：
- ✅ 10 种 Agent 模式
- ✅ 5 个 LLM Provider（OpenAI, Anthropic, Google, Azure, Bedrock）
- ✅ 中间件系统（retry, rate_limit, timeout, tracing, logging, langfuse）
- ✅ HTTP API 服务（REST + SSE + Dashboard）
- ✅ 技能系统（Codex SKILL.md 兼容）
- ✅ 多 Agent 编排（Swarm, Supervisor）
- ✅ DAG 图执行引擎 + 可视化编辑器
- ✅ Human-in-the-loop
- ✅ 结构化输出 / response_model
- ✅ MCP 客户端
- ✅ CLI 脚手架 + 评估命令
- ✅ Agent 评估框架（EvalSuite / EvalRunner / EvalReport）
- ✅ 流式 Agent 状态可视化（Web 控制台）
- ✅ DAG 可视化编辑器（交互式拖拽编辑）

进行中：
- ⬜ 更多 Provider
- ⬜ 增量编译
- ⬜ LangSmith / Weights & Biases 集成

---

## 📄 许可

Apache 2.0

---

<p align="center"><strong>锻造链</strong> — 锻造你的链。</p>
