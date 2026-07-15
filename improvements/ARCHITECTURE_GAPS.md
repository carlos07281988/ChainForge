# ChainForge 架构差距分析

> 对比 LangChain 核心架构与 Agent 生态前沿的差距分析。2026-07 版本。

---

## 一、最关键的架构差距

### 1. CyclicGraph — LangGraph 范式的图执行引擎

**现状**：`chainforge/core/graph.py` 实现的是经典**有向无环图 (DAG)** 执行引擎——拓扑排序后线性执行，不支持环。

**问题**：Agent 场景天然有环：
- Agent loop 本身是 cycle（think → act → observe → think）
- 自反思/修正循环（Reflection Agent 需要往返）
- 多 Agent 辩论/对话（来回通信）
- 工具执行失败后的重试/修正回路

**LangChain 的做法**：LangGraph 将 agent 的每个阶段（think/act/observe/route）建模为图节点，用 `add_conditional_edges(source, routing_fn)` 实现状态驱动的路由。图本身支持循环，不依赖拓扑排序。

**文件参考**：`chainforge/core/graph.py:DAG`

**建议方案**：
- 在现有 `core/graph.py` 基础上增加 `CyclicGraph` 类
- 支持 `add_conditional_edges(source, routing_fn)` — routing_fn 根据当前 state dict 决定下一步去向
- Node 类型区分为 `agent`, `tool`, `router`, `conditional`, `entry`, `exit`
- 图的**多轮执行**：run until stuck on a terminal node，而非一轮拓扑排序后退出
- `Agent._run_loop` 本身可以重构为一个 CyclicGraph 的执行实例

---

### 2. State Persistence / Checkpointing

**现状**：`chainforge/core/state.py` 的 `StateTracker` 只记录已发生的状态转换，纯内存，不做持久化。

**无法支持**：
- 断点恢复（agent 执行到一半保存/恢复）
- 跨轮次的**线程/会话状态管理**（类似 LangGraph thread_id）
- Debug 时的 step-back / state inspection
- 多用户场景下的会话隔离

**LangChain 的做法**：LangGraph 通过 `checkpointer`（支持 SQLite/Postgres/内存）在每个 node 执行后 checkpoint 整个 state dict。配合 `thread_id` 实现多会话管理。

**文件参考**：`chainforge/core/state.py:StateTracker`

**建议方案**：
- 在 `core/state.py` 引入 `Checkpointer` 抽象协议

```python
class Checkpointer(Protocol):
    async def save(self, state: dict, thread_id: str, checkpoint_id: str | None = None) -> str: ...
    async def load(self, thread_id: str, checkpoint_id: str | None = None) -> dict | None: ...
    async def list_threads(self) -> list[ThreadInfo]: ...
    async def list_checkpoints(self, thread_id: str) -> list[str]: ...
```

- 内置至少两个实现：InMemoryCheckpointer、SQLiteCheckpointer
- Agent 执行上下文从纯 `Message[]` 扩展到结构化 State Dict（含消息历史、中间变量、错误信息、执行元数据）
- `Agent.run()` 增加 `thread_id` 参数

---

## 二、多 Agent 拓扑的缺口

### 现状

| 模式 | 文件 | 状态 |
|------|------|------|
| Swarm（parallel/sequential/conference） | `orchestration/swarm.py` | ✅ |
| Supervisor（一级委派） | `orchestration/supervisor.py` | ✅ |
| AgentChain（线性链） | `agents/agent_chain.py` | ✅ |
| AgentTool（agent 作为 tool） | `agents/agent_tool.py` | ✅ |
| RouterAgent（意图路由） | `agents/router.py` | ✅ |
| AgentHub（注册/发现） | `agents/agent_hub.py` | ✅ |

### 缺失拓扑

| 模式 | LangGraph 对应 | 用途 |
|------|---------------|------|
| Network 自由通信 | 多 node 网状连接 | Agent 之间直接传递消息，不经 supervisor 仲裁 |
| Hierarchical teams | 多级 supervisor | CTO -> 经理 -> 工程师 三层委派 |
| Debate | 多 agent 辩论 | 多 agent 反复论辩后达成共识 |

### 具体建议
- `Swarm` 的 `_run_conference` 可扩展为 Debate/Network 模式，支持 agent 间非阻塞消息传递
- `Supervisor` 应支持嵌套：worker 本身也可以是 supervisor（递归委派）
- 新增 `orchestration/network.py`：所有 agent 可以广播消息、订阅 topic、点对点通信

---

## 三、Memory 链条上缺的几环

### 现状

| 内存类型 | 文件 | 状态 |
|---------|------|------|
| BufferMemory（短期滑动窗口） | `memory/buffer.py` | ✅ |
| VectorMemory（语义检索） | `memory/vector.py` | ✅ (in-memory only) |
| EntityMemory（实体跟踪） | `memory/entity.py` | ✅ (规则提取) |
| SummaryMemory | `memory/summary.py` | ⚠️ 名不副实，实际是滚动窗口 |
| MemoryManager | `memory/manager.py` | ✅ |

### 缺口

**1. 消息摘要/压缩**
- `context/compressor.py` 已有 CompressorStrategy，但无自动触发机制
- 没有类似 LangChain `trim_messages()` / `summarize_messages()` 的通用工具函数
- `ConversationalAgent.run()` 中有手动摘要逻辑，但无法在其他 agent 类型中复用

**2. 跨会话持久化**
- VectorMemory 目前只有 in-memory 实现
- 缺少 SQLite/Postgres 后端
- 不支持 `session_id` 隔离

**3. 知识图谱记忆（LangChain Neo4jMemory / GraphMemory）**
- EntityMemory 是简单的 key-value + 规则提取
- 没有将实体间关系建模为图结构
- 缺少 GraphRAG 风格的社区摘要增强检索

### 建议方案
- `MemoryManager` 增加 `summarize()` 方法，超出窗口时自动摘要旧消息
- VectorMemory 添加上持久化存储（至少 SQLite）
- EntityMemory 升级为轻量级图结构（邻居节点、关系类型）
- `SummaryMemory` 要么加 `compress(llm)` 方法，要么重命名为 `RollingMemory`

---

## 四、Tool 系统的可进化方向

### 对比 LangChain

| 功能 | ChainForge | LangChain |
|------|-----------|-----------|
| Tool 返回值类型 | 仅 `str` | `ToolMessage` + 任意 artifact |
| OpenAPI -> Tool 自动转换 | ❌ | ✅ `OpenAPIToolkit` |
| Retriever-as-Tool | ❌ | ✅ 内建 |
| 流式 Tool 执行 | ❌ | ✅ 支持 stream |
| Tool 运行时注入参数 | ❌ | ✅ `InjectedToolArg` |
| Tool 权限与集 | ✅ `ToolPermissionPolicy` | ✅ 类似 |

### 建议
- 允许 Tool 返回结构化数据（不限于 `str`），`ToolSpec` 增加 `response_schema` 字段
- 增加 `BaseTool` 基类（类似 LangChain），支持 `_run` / `_arun` 生命周期方法
- 添加 OpenAPIToolkit：传入 OpenAPI spec，自动生成工具集
- Tool 支持 artifact 模型：工具执行后产出的不仅是文本，还可以是文件/图片/结构化数据

---

## 五、Provider 与多模态

### 现状

| Provider | 文件 | 状态 |
|----------|------|------|
| OpenAI | `providers/openai.py` | ✅ |
| Anthropic | `providers/anthropic.py` | ✅ |
| Google | `providers/google.py` | ✅ |
| Azure | `providers/azure.py` | ✅ |
| Bedrock | `providers/bedrock.py` | ✅ |

### 缺口
- **本地推理**：Ollama、vLLM、LlamaCpp 缺失
- **视觉多模态**：Message 没有 image/audio/file parts 支持，Provider 也没有对应参数
- **Thinking/Reasoning tokens**：OpenAI o-series、DeepSeek-R1 输出含 `reasoning_content`，`LLMResponse` 没有字段接收
- **成本追踪**：缺少 aggregated cost 计算

### 建议
- `Message` 增加 `parts` 字段（类似 OpenAI 的 `content: list[{"type": "text"|"image_url"|"file"}]`）
- 添加 `OllamaProvider`（本地推理）
- `LLMResponse` 增加 `reasoning_content` 和 `cost` 字段
- Provider 级别增加 `supports_vision` / `supports_structured_output` 等能力声明

---

## 六、Evaluation 框架的深度

### 现状
存在完整的 EvalCase/EvalSuite/EvalRunner/EvalReport 框架，位于 `eval/` 目录。

### LangChain 有而缺的
- **LLM-as-judge**：内建 Judge/Evaluator LLM，自动对 agent 输出评分
- **Pairwise 对比**：两个 agent variant 背靠背对比 Elo 评分
- **LangSmith 集成**：trace -> eval -> dataset -> regression 完整闭环
- **对抗性测试**：prompt injection / jailbreak 场景测试

### 建议
- EvalRunner 扩展两种 eval 模式：
  1. `LLMJudgeEval` — 用另一个 LLM 对输出评分
  2. `PairwiseEval` — A/B 对比两个 agent 的输出

---

## 七、部署基础设施

### 现状
`server.py` 提供 FastAPI REST + SSE 端点，含 `/run`、`/stream`、Dashboard 路由。

### 生产级缺失

| 功能 | 说明 | 建议实现位置 |
|------|------|------------|
| 线程/会话管理 | 每个用户/对话使用独立 thread_id | `server.py` new router `/api/v1/threads` |
| Webhook | agent 执行完成后 POST 到预设 URL | `callbacks/` 新 Callback 实现 |
| 使用量追踪与限流 | 用户维度的配额管理 | `middleware/` 扩展 RateLimitMiddleware |
| 认证/授权 | API key 校验 | `server.py` 增加 dependency |
| Cron/定时任务 | 定期触发 agent 执行 | 新模块 `scheduler/` |

---

## 八、前沿方向

### 1. MCP 深度集成
现有 `mcp/` 是很好的起点。可扩展：
- MCP Server 注册 -> Tool 自动发现 -> Agent 动态加载
- 类似 OpenAI GPT Actions / Function Calling for external APIs

### 2. Computer Use（浏览器/桌面操作）
- Claude Computer Use / OpenAI Operator / Playwright Agent
- Agent 直接操作浏览器完成 UI 任务
- 建议：封装 PlaywrightTool 作为 chainforge tool

### 3. Thinking/Reasoning 模型支持
- DeepSeek-R1、Qwen-32B：输出 `reasoning_content` 和 `content` 两部分
- OpenAI o-series：`reasoning_tokens`
- `LLMResponse` 应有字段接收，Provider 层需要传递对应参数

### 4. Agentic RAG
- Self-RAG：agent **决定何时检索**
- Corrective RAG：agent **评估检索质量**并修正
- Adaptive RAG：agent **选择检索策略**
- 在 `rag/chains.py` 增加实现

### 5. 多 Agent 通信标准化
- MCP 为 tool 调用标准
- A2A 为 agent 间通信标准 (ChainForge 已有 A2A ✅)
- 建议：增加 A2A server 的 trace 集成（已有 Cross-Agent Tracing 计划）
