# ChainForge Phase 31: Agent Justice, Benchmarking & Federation

**日期：** 2026-07-28
**状态：** 已批准
**范围：** Agent Justice Protocol、Agent Benchmarking as Code、Agent Federation Protocol

---

## 设计约束

- **纯 SDK，零前端** — 所有模块通过 Python API 或 CLI 使用
- **不改变 Agent 核心 API**
- **可选、可组合** — 每模块独立可用
- **Pydantic BaseModel + Protocol-based interfaces**

---

## Module 1: Agent Justice Protocol

### API

```python
from chainforge.enterprise.justice import (
    JusticeGuard, EvidencePack, DecisionReview,
    AppealRequest, AppealVerdict,
)

# Agent 运行时自动收集证据包
agent = Agent(
    llm=llm, tools=[...],
    middlewares=[JusticeGuard(
        evidence_ttl_days=365,          # 证据保留期
        auto_generate_review=True,       # 被质疑时自动生成 review package
    )],
)

# 用户发起争议
appeal = AppealRequest(
    run_id="run-abc123",
    reason="The agent refunded only $50, but my order was $150",
    raised_by="user@example.com",
)

# 自动生成 Decision Review Package
review = justice.generate_review(appeal)
# → DecisionReview:
#   timeline: [input → llm_calls → tool_calls → output]
#   evidence: [provenance chain, complete messages, tool results]
#   decision_tree: "Why the agent chose refund_tool instead of full_refund"
#   suggested_action: "Human review recommended — possible tool selection error"

# Human Appeal
verdict = await justice.human_appeal(
    appeal=appeal,
    assigned_to="human-reviewer@acme.com",
    evidence=review,
)
# → AppealVerdict(upheld=True, override_action="full_refund", reason="...")
```

### 文件: `chainforge/enterprise/justice/` (5 files)

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `guard.py` | JusticeGuard middleware — 自动收集证据包 |
| `evidence.py` | EvidencePack — 完整证据链模型 |
| `review.py` | DecisionReview + DecisionTree — 决策复盘 |
| `appeal.py` | AppealRequest + AppealVerdict + Human Appeal engine |

---

## Module 2: Agent Benchmarking as Code

### API

```python
# chainforge.bench.yaml
# suite: customer-support
# agents:
#   v1:
#     llm: gpt-4o
#     tools: [query_db, send_email]
#   v2:
#     llm: gpt-4o-mini
#     tools: [query_db, send_email, generate_refund]
# scenarios:
#   - name: refund_request
#     input: "I want a refund for order #12345"
#     expect:
#       tool_calls_include: [query_db]
#       output_contains: "refund"
#       max_latency_ms: 5000
#       max_cost: 0.05
#   - name: missing_order
#     input: "Where is my order #99999?"
#     expect:
#       tool_calls_include: [query_db]
#       output_not_contains: "refund"
```

```python
# Python API
from chainforge.enterprise.bench import (
    BenchmarkSuite, BenchmarkRunner, RegressionDetector,
)

suite = BenchmarkSuite.load("chainforge.bench.yaml")
runner = BenchmarkRunner(suite)

# Run single agent benchmark
result = await runner.run(agent, scenario="refund_request")
print(f"Pass: {result.passed}, Latency: {result.latency_ms}ms, Cost: ${result.cost}")

# Run A/B comparison
comparison = await runner.compare(
    agent_a=agent_v1,
    agent_b=agent_v2,
    scenario="refund_request",
)
# → BenchmarkComparison:
#   v1: passed=True, latency=800ms, cost=$0.03
#   v2: passed=True, latency=300ms, cost=$0.01
#   winner: v2 (faster, cheaper, same accuracy)

# Regression detection
detector = RegressionDetector(baseline="v1-results.json")
regression = detector.check("v2-results.json")
# → RegressionReport:
#   regressed_scenarios: ["refund_request"] ← v2 在这个场景上退步了
#   improved_scenarios: ["missing_order"]
```

### 文件: `chainforge/enterprise/bench/` (4 files)

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `suite.py` | BenchmarkSuite — YAML/JSON 加载 |
| `runner.py` | BenchmarkRunner — 执行 + 比对 |
| `regression.py` | RegressionDetector — 自动回归检测 |

---

## Module 3: Agent Federation Protocol

### API

```python
from chainforge.enterprise.federation import (
    FederatedAgent, AgentExport, InteropEndpoint,
)

# 导出 ChainForge agent 为框架无关的 HTTP endpoint
export = AgentExport(
    agent=my_agent,
    protocol="chainforge-interop-v1",
)
export.serve(port=9100)
# → 外部 agent (LangChain / CrewAI / AutoGen) 可以直接调这个 endpoint

# 导入外部框架的 agent 为 ChainForge agent
external = FederatedAgent(
    endpoint="https://langchain-agent.internal/agent",
    protocol="chainforge-interop-v1",  # 或 "a2a-v1" (Google A2A)
)
# external 现在可以像普通 ChainForge agent 一样使用:
# agent = Agent(llm=llm, tools=[external])  ← 外部 agent 作为 tool
# pipeline = Pipeline() >> my_agent >> external  ← 外部 agent 参与管道

# Interop Protocol 定义
# POST /agent
# Request:
# {
#   "messages": [{"role": "user", "content": "..."}],
#   "tools": [{"name": "...", "description": "...", "parameters": {...}}],
#   "context": {"run_id": "...", "parent_agent": "..."}
# }
# Response (SSE):
#   event: text, data: "Hello"
#   event: tool_call, data: {"name": "search", "arguments": {...}}
#   event: done, data: {"content": "...", "usage": {...}}
```

### 文件: `chainforge/enterprise/federation/` (4 files)

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `protocol.py` | Interop Protocol 定义 (JSON Schema) |
| `export.py` | AgentExport — 导出 ChainForge agent 为 endpoint |
| `import_.py` | FederatedAgent — 导入外部 agent |

---

## 交付物汇总

| 模块 | 文件数 | 核心 API |
|------|--------|----------|
| Justice Protocol | 5 | JusticeGuard, EvidencePack, DecisionReview, AppealRequest, AppealVerdict |
| Benchmarking as Code | 4 | BenchmarkSuite, BenchmarkRunner, RegressionDetector |
| Federation Protocol | 4 | FederatedAgent, AgentExport, InteropEndpoint |
| **总计** | **~13 files, ~1,500 lines** | — |

## 实施顺序

```
Justice (#1) → Benchmarking (#2) → Federation (#3)
```

理由：Justice 最独立，直接使用已有的 ProvenanceTracker + Governance 2.0 数据；Benchmarking 使用 Justice 的 EvidencePack 作为 bench 评估数据源；Federation 最后因为它的 interop endpoint 需要暴露前两个模块的能力。
