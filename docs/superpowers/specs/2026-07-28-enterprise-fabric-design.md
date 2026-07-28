# ChainForge Enterprise Fabric — 四模块设计规范

**日期：** 2026-07-28
**状态：** 已批准
**范围：** Agent Economics Layer、EU AI Act Compliance Engine、Agent Supply Chain Security、Collective Agent Memory

---

## 设计约束

- **纯 SDK，零前端** — 所有模块通过 Python API 使用，`chainforge serve` 可选消费
- **Middleware 优先** — 功能以 middleware/plugin 形式嵌入 Agent，不改变 Agent 核心 API
- **可选、可组合** — 每个模块独立可用，互不强制依赖
- **遵循已有模式** — Pydantic BaseModel、Protocol-based interfaces、lazy import

---

## Module 1: Agent Economics Layer

### 设计目标

企业和平台方需要知道：哪个 agent 花了多少钱？归属于哪个部门？能否设定预算上限自动控费？

### API 设计（纯编程接口，无 UI）

```python
from chainforge.enterprise.economics import (
    CostTracker,
    BudgetGuard,
    TokenLedger,
    Attribution,
    CostReport,
)

# ── 1. 成本追踪 ──────────────────────────────────────────

tracker = CostTracker(
    backend="sqlite",            # "sqlite" | "memory" | "custom"
    db_path="costs.db",
)

# 每个 LLM 调用自动记录
# 从 LLMResponse.usage + LLMResponse.cost 中提取，无需手动埋点
agent = Agent(
    llm=SmartRouter(...),
    middlewares=[tracker.middleware(attribution={
        "project": "customer-support",
        "department": "operations",
        "tenant": "acme-corp",
    })],
)

# ── 2. 成本查询 ──────────────────────────────────────────

# 按项目汇总本月成本
report = tracker.report(
    group_by="project",
    period=("2026-07-01", "2026-07-28"),
)
# → CostReport: total=$152.70, rows=[{project, calls, tokens, cost}]

# 按模型拆分
report = tracker.report(group_by="model", period="today")

# 按租户拆分（多租户平台场景）
report = tracker.report(group_by="tenant", period="this-month")

# 导出 JSON
data = report.to_json()   # → list[dict], 可直接送 Grafana/DataDog

# ── 3. 预算控制 ──────────────────────────────────────────

agent = Agent(
    llm=SmartRouter(...),
    middlewares=[
        BudgetGuard(
            daily_limit=50.0,
            on_limit="downgrade",     # "downgrade" | "block" | "warn"
            fallback_model="gpt-4o-mini",
            tracker=tracker,          # 复用同一个 tracker
        ),
    ],
)

# ── 4. 优化建议（分析历史数据）─────────────────────────────

suggestions = tracker.optimize(period="last-30-days")
# → CostOptimization(
#     potential_savings=340.50,
#     items=[
#       "Switch 12,000 'hello' queries from gpt-4o → gpt-4o-mini: save $240",
#       "Cache repeated weather queries (8,000 calls): save $100.50",
#     ]
#   )
```

### 文件结构

```
chainforge/enterprise/economics/
├── __init__.py          # 导出 CostTracker, BudgetGuard, TokenLedger, CostReport
├── tracker.py           # CostTracker — 核心里程碑记录
├── guard.py             # BudgetGuard — 预算控制 middleware
├── attribution.py       # Attribution — 成本归因标签模型
├── report.py            # CostReport, CostOptimization — 报表与优化建议
└── ledger.py            # TokenLedger — 底层存储 (sqlite/memory)
```

### 数据模型

```python
class CostRecord(BaseModel):
    """单次调用成本记录"""
    timestamp: float
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost: float
    duration_ms: float
    attribution: dict[str, str]  # {"project": "x", "department": "y"}

class BudgetGuard(BaseModel):
    """预算守护中间件"""
    daily_limit: float
    on_limit: str = "downgrade"  # downgrade | block | warn
    fallback_model: str | None = None
    tracker: CostTracker | None = None
```

---

## Module 2: EU AI Act Compliance Engine

### 设计目标

2026 年 EU AI Act 全面生效。企业部署 agent 前需要：
1. 知道自己的 agent 属于哪个风险等级
2. 高风险 agent 必须有 HITL
3. 能输出合规审计报告

### API 设计（纯编程接口）

```python
from chainforge.enterprise.compliance import (
    ComplianceGuard,
    RiskClassifier,
    ComplianceAuditor,
    HITLPolicy,
)

# ── 1. 自动风险分级 ───────────────────────────────────────

classifier = RiskClassifier(
    rules=[
        # 内置规则 + 自定义覆盖
        RiskRule(tool_contains="delete", risk="high"),
        RiskRule(tool_contains="write_file", risk="high"),
        RiskRule(data_labels=["pii"], provider_cloud=True, risk="high"),
        RiskRule(domain="healthcare", risk="high"),
        RiskRule(domain="legal", risk="limited"),
    ]
)

# ── 2. 合规守护中间件 ─────────────────────────────────────

agent = Agent(
    llm=llm,
    tools=[delete_file, query_db],
    middlewares=[
        ComplianceGuard(
            classifier=classifier,
            hitl_policy=HITLPolicy(
                require_approval_on=["high"],   # 高风险 → 强制人工审批
                approval_handler=my_approval_fn, # 自定义审批流程
            ),
            auditor=ComplianceAuditor(
                log_path="compliance.db",
                regulation="eu-ai-act-2026",
            ),
        ),
    ],
)

# ── 3. 审计报告导出 ───────────────────────────────────────

auditor = ComplianceAuditor(regulation="eu-ai-act-2026")
report = auditor.generate(
    period=("2026-01-01", "2026-07-28"),
    format="json",            # "json" | "markdown" | "pdf_ready_dict"
)
# → ComplianceReport:
#     risk_tier: "high"
#     articles: [
#       {article: 11, requirement: "Technical documentation", status: "compliant"},
#       {article: 12, requirement: "Record-keeping", status: "compliant"},
#       {article: 13, requirement: "Transparency", status: "compliant"},
#       {article: 14, requirement: "Human oversight", status: "non_compliant",
#        detail: "High-risk agent 'delete_files_agent' has no HITL configured"},
#     ]
#     recommendations: ["Enable HITL for delete_files_agent"]

# 给合规官看的 markdown
print(report.to_markdown())

# 对接 DevOps 管道
report_dict = report.to_json()
```

### 文件结构

```
chainforge/enterprise/compliance/
├── __init__.py          # 导出 ComplianceGuard, RiskClassifier, ComplianceAuditor, HITLPolicy
├── guard.py             # ComplianceGuard middleware
├── classifier.py        # RiskClassifier + RiskRule
├── auditor.py           # ComplianceAuditor + ComplianceReport
├── hitl.py              # HITLPolicy + approval handler protocol
└── regulations/         # 法规模板
    ├── __init__.py
    └── eu_ai_act.py     # EU AI Act article checklists
```

---

## Module 3: Agent Supply Chain Security

### 设计目标

Agent 的 tool/skill/MCP server 依赖链有安全风险。需要一个：
1. 扫描工具链 → 知道每个 tool 引入的依赖
2. 运行 MCP server 的行为 fingerprint
3. 生成最小权限 policy
4. 导出 SBOM

### API 设计（纯编程接口）

```python
from chainforge.enterprise.supply_chain import (
    SupplyChainScanner,
    PermissionPolicy,
    SBOMExporter,
    MCPVerifier,
)

# ── 1. 扫描 Agent 的供应链 ─────────────────────────────────

scanner = SupplyChainScanner()
report = scanner.scan(agent)
# → SupplyChainReport:
#     tools: [
#       {name: "send_email", deps: ["smtplib", "email"], cves: []},
#       {name: "delete_file", deps: ["os", "shutil"], cves: []},
#     ]
#     skills: [...]
#     mcp_servers: [
#       {url: "http://mcp-weather:8080", risk: "medium",
#        reason: "Sends data to external domain api.weather.com"},
#     ]
#     total_risk_score: 4.2 / 10

# ── 2. 生成最小权限策略 ────────────────────────────────────

policy = scanner.recommend_policy(agent)
# → PermissionPolicy:
#     allowed_tools: ["send_email", "query_db"]
#     blocked_tools: ["delete_file"]
#     mcp_constraints: {
#       "weather-api": {"max_data_transfer_mb": 1, "allow_external": False},
#     }

# 写入 YAML 文件
policy.to_yaml("security/agent-policies/customer_service.yaml")

# ── 3. Runtime 策略执行 ────────────────────────────────────

agent = Agent(
    llm=llm,
    tools=[...],
    middlewares=[
        policy.as_middleware(),   # 自动拦截越权调用
    ],
)

# ── 4. 导出 SBOM ───────────────────────────────────────────

sbom = SBOMExporter().export(
    agent=agent,
    format="spdx",            # "spdx" | "cyclonedx"
)
sbom.save("sbom.customer_service.spdx.json")
```

### 文件结构

```
chainforge/enterprise/supply_chain/
├── __init__.py          # 导出所有符号
├── scanner.py           # SupplyChainScanner +SupplyChainReport
├── policy.py            # PermissionPolicy
├── sbom.py              # SBOMExporter
├── mcp_verifier.py      # MCPVerifier — MCP server 行为指纹
└── dependency.py        # 依赖树分析 + CVE 查询
```

---

## Module 4: Collective Agent Memory

### 设计目标

多个 agent 共享学习。每次执行结果（成功/失败/成本/工具选择）自动沉淀到共享 memory，新 agent 启动时检索相关经验。

### API 设计（纯编程接口）

```python
from chainforge.enterprise.collective import (
    CollectiveMemory,
    ExperienceRecorder,
    ExperienceRetriever,
    ConflictResolver,
)

# ── 1. 创建共享记忆 ──────────────────────────────────────

cm = CollectiveMemory(
    backend="qdrant",            # "qdrant" | "chroma" | "sqlite"
    namespace="customer-support",
    forgetting_curve="ebbinghaus",  # 经验自动衰减
)

# ── 2. Agent 自动记录经验 ─────────────────────────────────

agent = Agent(
    llm=llm,
    tools=[...],
    collective_memory=cm,     # 省心：自动记录+自动检索
)

# ── 3. 主动检索（可选，给高级用户深度控制）───────────────

retriever = ExperienceRetriever(memory=cm)
similar = retriever.search(
    task="refund a customer order",
    limit=5,
    min_success_rate=0.7,
)
for exp in similar:
    print(f"{exp.task} → {exp.outcome} (cost: ${exp.cost})")

# ── 4. 冲突解决 ──────────────────────────────────────────

resolver = ConflictResolver(memory=cm)
conflicts = resolver.find_conflicts()
# → [ConflictResolution(
#       task_type="refund_request",
#       agent_a: "always send email after refund",
#       agent_b: "refund only, no email needed",
#       resolution: "email reduces customer complaints by 60% → recommend email",
#       confidence: 0.92,
#   )]

# ── 5. 导出团队经验（给 PM/运营看）───────────────────────

dump = cm.export(format="json")
# → [Experience(task=..., tools_used=[...], cost=..., success=True/False), ...]
```

### 文件结构

```
chainforge/enterprise/collective/
├── __init__.py          # 导出所有符号
├── memory.py            # CollectiveMemory — 核心
├── recorder.py          # ExperienceRecorder — 自动记录 middleware
├── retriever.py         # ExperienceRetriever — 语义检索
├── resolver.py          # ConflictResolver — 冲突仲裁
├── forgetting.py        # ForgettingCurve — 时间衰减算法
└── experience.py        # Experience 数据模型
```

### 数据模型

```python
class Experience(BaseModel):
    """一条共享经验"""
    id: str
    task: str                    # 原始用户请求摘要
    task_type: str               # "refund_request" | "qa" | "code_gen" ...
    tools_used: list[str]
    model_used: str
    outcome: str                 # "success" | "failure" | "partial"
    feedback: str | None         # 人工反馈（可选）
    cost: float
    tokens: int
    duration_ms: float
    timestamp: float
    decay_factor: float = 1.0    # 随时间衰减
```

---

## 交付物汇总

| 模块 | 文件数 | 核心 API 入口 |
|------|--------|--------------|
| Economics | `enterprise/economics/` (5 files) | `CostTracker`, `BudgetGuard`, `CostReport` |
| Compliance | `enterprise/compliance/` (5 files) | `ComplianceGuard`, `RiskClassifier`, `ComplianceAuditor` |
| Supply Chain | `enterprise/supply_chain/` (5 files) | `SupplyChainScanner`, `PermissionPolicy`, `SBOMExporter` |
| Collective Memory | `enterprise/collective/` (6 files) | `CollectiveMemory`, `ExperienceRecorder`, `ConflictResolver` |
| **总计** | **~21 files, ~2,500 lines** | — |

## 设计约束

- `chainforge/enterprise/` 使用 lazy import — 不 import 不下发依赖
- 每个模块的 middleware 通过 `Agent(middlewares=[...])` 集成
- 数据存储后端默认为 sqlite，支持自定义
- 所有 report/model 提供 `.to_json()` / `.to_dict()` 导出——不做 HTML/CSS

## 实施顺序

```
Module 2 (Compliance) → Module 1 (Economics) → Module 4 (Collective) → Module 3 (Supply Chain)
```

理由：Compliance 最早做，因为它对 Governance 2.0 的依赖性最强；Economics 次之因为它给 Compliance 贡献成本数据；Collective Memory 为 Economics 的优化建议提供数据源；Supply Chain 做最后因为它扫描的对象包含了前三个模块的产物。
