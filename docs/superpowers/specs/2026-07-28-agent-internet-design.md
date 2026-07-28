# ChainForge Phase 30: Agent Internet — 五模块设计规范

**日期：** 2026-07-28
**状态：** 已批准
**范围：** Agent Identity, Economic Protocol, Capability Registry, Durable Execution, Data Lineage

---

## 设计约束

- **纯 SDK，零前端** — 所有模块通过 Python API 使用
- **Middleware/Pydantic Plugin 优先** — 不改变 Agent 核心 API
- **可选、可组合** — 每模块独立可用，互不强制
- **Pydantic BaseModel + Protocol-based interfaces + lazy import**

---

## Module 1: Agent Identity & Reputation Protocol

### API

```python
from chainforge.enterprise.identity import (
    AgentIdentity, IdentityRegistry, ReputationEngine,
    TrustPolicy, VerifiableCredential, ReputationScore,
)

# Agent 生成 Ed25519 身份
identity = AgentIdentity.create(
    agent_name="customer-support-bot",
    organization="acme-corp",
    capabilities=["customer_service", "refund_processing"],
)
# → agent_id="cf-a1b2c3d4", public_key, private_key, did

# Agent 集成
agent = Agent(
    llm=llm, identity=identity,
    trust_policy=TrustPolicy(rules=[
        TrustRule(min_reputation=70, action="allow"),
        TrustRule(max_reputation=50, action="block_all_tools"),
    ]),
)

# 每次 tool call 自动签名 X-Agent-Id + X-Agent-Signature header

# 信誉引擎
engine = ReputationEngine()
engine.record_event(agent_id, "successful_call", latency_ms=120)
engine.record_event(agent_id, "prompt_injection_attempt", severity="critical")
score = engine.score(agent_id)  # → ReputationScore(overall=92/100, ...)

# 跨组织凭证
credential = VerifiableCredential.issue(
    issuer=my_identity, subject="cf-a1b2c3d4",
    claims={"organization": "acme-corp", "valid_until": "2026-12-31"},
)
assert credential.verify(issuer_public_key=my_identity.public_key)
```

### 文件: `chainforge/enterprise/identity/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `identity.py` | AgentIdentity (Ed25519 生成/签名/验证, DID) |
| `registry.py` | IdentityRegistry (身份注册/查询/撤销) |
| `reputation.py` | ReputationEngine + ReputationScore |
| `trust.py` | TrustPolicy + TrustRule |
| `credential.py` | VerifiableCredential (签发/验证/过期) |

---

## Module 2: Agent Economic Protocol

### API

```python
from chainforge.enterprise.economy import (
    AgentEconomy, CreditLedger, BillingContract, Invoice, Transaction,
)

economy = AgentEconomy(settlement_currency="usd")

seller_agent = Agent(
    llm=llm, tools=[expensive_gpu_tool],
    economy=economy, economy_role="seller",
    billing_contract=BillingContract(pricing={"per_tool_call": 0.05}),
)

buyer_agent = Agent(
    llm=llm, economy=economy, economy_role="buyer", credit_limit=100.0,
)

# buyer 调用 seller 的工具 → Transaction 自动记录

buyer_invoice = economy.invoice(buyer_agent, period="this-month")
# → Invoice(total_payable=$12.50, items=[...])

seller_revenue = economy.revenue(seller_agent, period="this-month")
# → RevenueReport(total_earned=$10.00)

economy.settle(from_agent=buyer, to_agent=seller, amount=10.00, method="internal")
```

### 文件: `chainforge/enterprise/economy/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `engine.py` | AgentEconomy (交易协调、结算) |
| `ledger.py` | CreditLedger (账本记录、余额查询) |
| `contract.py` | BillingContract (定价模型) |
| `invoice.py` | Invoice + RevenueReport (账单/收入报表) |
| `middleware.py` | 自动拦截跨 agent 调用的 billing middleware |

---

## Module 3: Agent Capability Registry

### API

```python
from chainforge.enterprise.registry import (
    CapabilityRegistry, AgentProfile, CapabilityQuery,
    AutoNegotiation, ServiceLevelAgreement,
)

registry = CapabilityRegistry(backend="postgres", namespace="acme-corp")

profile = AgentProfile(
    agent_id="cf-a1b2c3d4", name="PostgreSQL Agent", version="2.1.0",
    capabilities=["postgresql:query", "postgresql:schema", "sql:generate"],
    tools_exposed=["query_db", "get_schema", "generate_sql"],
    endpoints={"a2a": "a2a://db-agent.acme.com/agent"},
    health_check_url="https://db-agent.acme.com/health",
    pricing={"per_query": 0.001},
    sla=ServiceLevelAgreement(max_latency_ms=500, availability=0.999),
)
registry.register(profile)

# Capability discovery
matches = registry.discover(capability="postgresql:query", min_availability=0.99)

# 模糊语义发现
matches = registry.discover(query="I need someone who can work with databases")

# 自动协商
negotiation = AutoNegotiation(
    requester=agent_a, capability_needed="postgresql:query",
    constraints={"max_cost_per_call": 0.01, "max_latency_ms": 500},
)
result = await negotiation.start()
# → result.provider, result.contract (pricing + SLA)

# 版本化 + 优雅下线
registry.deprecate("cf-a1b2c3d4", version="2.1.0", sunset_date="2026-08-15")
```

### 文件: `chainforge/enterprise/registry/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `profile.py` | AgentProfile + ServiceLevelAgreement |
| `registry.py` | CapabilityRegistry (注册/发现/下线/健康检查) |
| `discovery.py` | CapabilityQuery + 语义搜索匹配 |
| `negotiation.py` | AutoNegotiation (广播/筛选/握手) |
| `server.py` | `serve()` 方法 — HTTP API for external registry peers |

---

## Module 4: Durable Agent Execution

### API

```python
from chainforge.enterprise.durable import (
    DurableExecutor, ExecutionJournal, JobHandle,
    CrashRecoveryPolicy, DeadLetterQueue,
)

executor = DurableExecutor(
    backend="redis",                 # redis | postgres | etcd
    checkpoint_every=30,             # 每 30 秒 checkpoint
    crash_recovery=CrashRecoveryPolicy(auto_retry=True, max_retries=3),
)

# 同步模式
result = await executor.run_sync(agent, "审计我所有的 AWS S3 bucket")

# 异步模式
job: JobHandle = await executor.submit(agent, "处理 10 万条用户反馈")
status = await executor.status(job.job_id)
# → JobStatus(progress=0.67, elapsed="2h15m", estimated_remaining="1h08m")
result = await executor.wait(job.job_id, timeout=3600)

# 崩溃恢复 — 自动从最后一个 checkpoint 续跑

# 死信队列
dlq = DeadLetterQueue(backend="redis")
agent = Agent(llm=llm, failure_policy={"tool_crash": "dlq"}, dead_letter_queue=dlq)
dlq.list()  # 查看失败的任务
dlq.retry(job_id)  # 手动重试

# 执行日志
journal = ExecutionJournal("redis")
journal.trace(job_id)  # 完整执行追踪
journal.cost_at_checkpoint("chk-3")  # 某检查点累计成本

# 回调
executor = DurableExecutor(
    on_complete=lambda j: slack.send(f"✅ {j.job_id} done"),
    on_failure=lambda j, e: pagerduty.alert(f"❌ {j.job_id} failed"),
)
```

### 文件: `chainforge/enterprise/durable/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `executor.py` | DurableExecutor (run_sync/submit/status/wait/cancel/resume) |
| `checkpoint.py` | Checkpoint 模型 + 保存/恢复逻辑 |
| `journal.py` | ExecutionJournal (步骤追踪/查询) |
| `dlq.py` | DeadLetterQueue (失败任务存储/重试/丢弃) |
| `handle.py` | JobHandle + JobStatus |
| `recovery.py` | CrashRecoveryPolicy + 恢复策略 |

---

## Module 5: Agent Data Lineage & GDPR Right-to-Forget

### API

```python
from chainforge.enterprise.lineage import (
    DataLineageTracker, LineageQuery, ErasureRequest,
    DataSubject, ErasureReport, DeletionProof,
)

tracker = DataLineageTracker(backend="postgres")

agent = Agent(
    llm=llm, tools=[...], middlewares=[tracker.middleware()],
)

# 查询数据足迹
footprint = tracker.query(LineageQuery(
    data_subject=DataSubject(email="carlos@example.com"),
))
# → DataFootprint: 在 6 个系统中找到该用户痕迹

# 执行删除
request = ErasureRequest(
    data_subject=DataSubject(email="carlos@example.com"),
    reason="GDPR Article 17", requested_by="dpo@acme.com", deadline_hours=72,
)
report = await tracker.erase(request)
# → ErasureReport(status="partial", completed=4/6, pending=2)

# 删除证明
proof = DeletionProof(report)
proof.export("deletion-proof-carlos-2026.pdf")

# 自定义删除 handler
tracker.register_handler(location_type="vector_memory", handler=my_handler)
tracker.register_handler(location_type="custom_crm", handler=crm_deletion_fn)
```

### 文件: `chainforge/enterprise/lineage/`

| 文件 | 职责 |
|------|------|
| `__init__.py` | 导出 |
| `tracker.py` | DataLineageTracker (middleware + query + erase) |
| `query.py` | LineageQuery + DataSubject + DataFootprint + DataLocation |
| `erasure.py` | ErasureRequest + ErasureReport + ErasureItem + handler registry |
| `proof.py` | DeletionProof (sign/export/verify) + tamper-evident hashing |

---

## 交付物汇总

| 模块 | 文件数 | 核心 API |
|------|--------|----------|
| Identity & Reputation | 5 | AgentIdentity, ReputationEngine, TrustPolicy, VerifiableCredential |
| Economic Protocol | 5 | AgentEconomy, CreditLedger, BillingContract, Invoice |
| Capability Registry | 5 | CapabilityRegistry, AgentProfile, AutoNegotiation |
| Durable Execution | 6 | DurableExecutor, JobHandle, Checkpoint, DeadLetterQueue |
| Data Lineage & GDPR | 4 | DataLineageTracker, ErasureRequest, DeletionProof |
| **总计** | **~25 files, ~2,800 lines** | — |

## 实施顺序

```
Identity (#2) → Economic (#1) → Registry (#4) → Durable (#3) → Lineage (#5)
```

理由:
- Identity 是基础 — 所有需要验证 agent 身份的模块依赖它 (Economy, Registry)
- Economy 依赖 Identity 来验证交易双方
- Registry 同时依赖 Identity (验证注册) 和 Economy (定价协商)
- Durable 相对独立，但使用 Identity 来标记 job 的发起 agent
- Lineage 最后 — 它消费 Durable 的 checkpoint 和 Registry 的发现结果

## 集成架构

```
                   Identity (#2) ← 所有模块的基础
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   Economy (#1)    Registry (#4)   Durable (#3)
        │               │               │
        └───────────────┼───────────────┘
                        │
                   Lineage (#5)
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   Compliance     Supply Chain    Collective Memory
   (已有)         (已有)           (已有)
```
