# ChainForge 差距分析 V2 — 第二轮进化

> 继 Phase 11 实现后的第二轮差距分析。2026-07 版本。

---

## ✅ 已完成项（Phase 11 成果）

| # | 功能 | 状态 | 文件 |
|---|------|------|------|
| 1 | CyclicGraph 条件路由 | ✅ | core/graph.py |
| 2 | Checkpoint 协议 (InMemory/SQLite) | ✅ | core/state.py |
| 3 | TimeTravelDebugger | ✅ | core/time_travel.py |
| 4 | ConsensusAgent (4 种策略) | ✅ | orchestration/consensus.py |
| 5 | SelfEvolvingAgent | ✅ | agents/self_evolving.py |
| 6 | Agent.run() thread_id | ✅ | core/agent.py |

---

## 一、与 LangChain 的剩余差距

### 1.1 可视化调试器 (LangGraph Studio 等价)

现状：TimeTravelDebugger 提供 CLI 级调试。建议基于 FastAPI + React 构建 Web 界面。

### 1.2 声明式 Workflow DSL

现状：CyclicGraph 仅支持 Python 代码。建议支持 YAML/JSON 定义工作流。

### 1.3 文档加载器生态
现状：仅 PDF/GitHub/Notion。建议采用 unstructured 库。

### 1.4 嵌入模型 + 向量存储后端
现状：仅 IdentityEmbedding。建议 OpenAIEmbedding + Chroma/FAISS。

---

## 二、Agent 生态前沿

### 2.1 MCP 深度集成
现状：缺 MCP 服务器生命周期管理、自动发现、健康检查。

### 2.2 多模态输入管道
现状：Message 有 ContentPart但无统一处理管道。

### 2.3 Agent 安全性 (OWASP LLM Top 10)
现状：缺 Prompt Injection 检测、PII 脱敏。

---

## 三、逆天功能 — 市场上不存在的

### #1: 自适应工具合成 (Adaptive Tool Synthesis)
Agent 在运行时按需合成新工具。任何框架都没有。工作量 5-7 天。

### #2: 执行溯源图 (Execution Provenance Graph)
每个动作记录“为什么发生”。工作量 5-7 天。

### #3: 梦境/模拟模式 (Dream / Simulation Mode)
Agent 执行前先预测结果，对比实际结果并学习。工作量 8-10 天。

### #4: Agent 科技树 (Technology Tree)
借鉴文明游戏的科技树概念。工作量 8-10 天。

### #5: 液态时序记忆 (Liquid Time-Series Memory)
搾弃固定 token 窗口，采用连续衰减/增强记忆权重。工作量 6-8 天。

### #6: 多代 Agent 演化 (Multi-Generational Evolution)
种群式并行探索，基于遗传算法。工作量 10-14 天。

### #7: NL → CyclicGraph JIT 编译器
自然语言描述工作流→自动编译为 CyclicGraph。工作量 14-21 天。

---

## 四、优先级建议

| 优先级 | 功能 | 工作量 | 差异价值 |
|--------|------|--------|---------|
| P0 | 可视化 Agent Debugger UI | 7-10d | ★★★★★ |
| P0 | 自适应工具合成 | 5-7d | ★★★★★ |
| P1 | 执行溯源图 | 5-7d | ★★★★ |
| P1 | 梦境模拟模式 | 8-10d | ★★★★★ |
| P1 | 液态时序记忆 | 6-8d | ★★★★ |
| P2 | 声明式 Workflow DSL | 5-7d | ★★★★ |
| P2 | Agent 科技树 | 8-10d | ★★★★★ |
| P2 | 多代 Agent 演化 | 10-14d | ★★★★★ |
| P3 | NL → CyclicGraph 编译器 | 14-21d | ★★★★★ |
| P3 | 多模态输入管道 | 5-7d | ★★★ |
| P3 | Prompt Injection 检测 | 3-5d | ★★★★ |
