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
- [架构](#-架构)
- [代理模式](#-代理模式-10-种)
- [代理链接](#-代理链接)
- [日志](#-日志)
- [技能系统](#-技能系统)
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

## 🏗 架构

```
chainforge/
├── core/              # 核心：Agent, LLM, Message, Stream, Pipeline, Middleware
├── providers/         # LLM 实现：OpenAI, Anthropic, Google, Azure, Bedrock
├── agents/            # 10 种 Agent 模式
├── tools/             # 工具系统：@tool 装饰器
├── memory/            # 记忆：BufferMemory, SummaryMemory
├── middleware/        # 中间件：retry, rate_limit, timeout, logging, tracing
├── tracing/           # 链路追踪
├── skills/            # 技能加载/注册
├── mcp/               # Model Context Protocol 客户端
├── server.py          # HTTP API 服务
└── client.py          # HTTP 客户端
```

### 执行流程

```
用户输入 → Agent.run() → LLM.generate() → 有工具调用？
    ↓                        ↓
  是 → 执行工具 → 追加结果 → LLM.generate() → ...
    ↓
  否 → 输出文本 → 完成
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

## 🗺 路线图

已实现：
- ✅ 10 种 Agent 模式
- ✅ 5 个 LLM Provider（OpenAI, Anthropic, Google, Azure, Bedrock）
- ✅ 中间件系统（retry, rate_limit, timeout, tracing, logging）
- ✅ HTTP API 服务（REST + SSE）
- ✅ 技能系统（Codex SKILL.md 兼容）
- ✅ 多 Agent 编排（Swarm, Supervisor）
- ✅ DAG 图执行引擎
- ✅ Human-in-the-loop
- ✅ 结构化输出 / response_model
- ✅ MCP 客户端
- ✅ CLI 脚手架

进行中：
- ⬜ Langfuse / OpenTelemetry 集成（已完成中间件）
- ⬜ Agent 评估框架
- ⬜ 更多 Provider

---

## 📄 许可

Apache 2.0

---

<p align="center"><strong>锻造链</strong> — 锻造你的链。</p>
