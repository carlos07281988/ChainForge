# Phase 30: Agent Internet 实施计划

> **面向协作工作者：** 所需子技能：使用 superpowers:subagent-driven-development 逐任务实施，每步后用测试验证，每个任务后提交，最后进行整体系统审核。

**目标：** 为 ChainForge 构建 Agent Internet 五项能力：身份与信誉、经济协议、能力注册、持久化执行、GDPR 数据血缘。

**架构：** `chainforge/enterprise/` 新增五个子包，按依赖顺序依次实施。纯 SDK，不含 UI。所有组件通过中间件和可选参数集成。

**技术栈：** Python 3.12+、Pydantic、sqlite3 / Redis 可选、httpx、cryptography (Ed25519)、hashlib

---

## 全局约束

- 所有新文件均包含 `from __future__ import annotations`
- Apache 2.0 许可证头
- 所有 Pydantic 模型使用 `ConfigDict(arbitrary_types_allowed=True)`
- 纯 SDK — `.to_json()` / `.model_dump()` 导出；无 HTML/CSS
- 中间件集成 — `Agent(middlewares=[...])` 用于每模块
- 可选依赖 — `cryptography`、`redis` 和 `httpx` 为可选附加项
- 实施顺序：Identity → Economy → Registry → Durable → Lineage

---

## 阶段一：Agent 身份与信誉协议

理由：身份是所有其他模块的基础。Economy 和 Registry 都需要签名验证。

**任务 1.1：创建身份基础（Ed25519 密钥生成 + 签名 + DID）**

文件：
- 创建 `chainforge/enterprise/identity/__init__.py`
- 创建 `chainforge/enterprise/identity/identity.py`

核心类签名：
```python
class AgentIdentity(BaseModel):
    agent_id: str           # "cf-a1b2c3d4"
    name: str
    organization: str
    public_key: str         # Ed25519 hex
    capabilities: list[str]
    created_at: float
    # --- 内部 ---
    _private_key: str       # 从不序列化

    @classmethod
    def create(cls, name, org, capabilities) -> "AgentIdentity":
        """生成 Ed25519 密钥对，返回身份。"""
    def sign(self, payload: bytes) -> str:
        """使用 Ed25519 私钥签名。返回十六进制签名。"""
    @staticmethod
    def verify(payload: bytes, signature: str, public_key: str) -> bool:
        """使用 Ed25519 公钥验证签名。"""
    @property
    def did(self) -> str:         # "did:chainforge:cf-a1b2c3d4"
    def to_json(self) -> dict:    # 公钥字段，仅用于导出，私钥除外
```

**任务 1.2：创建信誉引擎**

文件：
- 创建 `chainforge/enterprise/identity/reputation.py`

核心类：
```python
class ReputationScore(BaseModel):
    agent_id: str
    overall: int         # 0-100，综合得分
    reliability: int     # 成功率加权
    latency: int         # 速度得分
    safety: int          # 注入 / 恶意行为扣分
    accuracy: int        # 工具选择正确率
    total_calls: int
    incident_count: int

class ReputationEngine:
    def __init__(self): ...
    def record_event(self, agent_id, event_type, **data) -> None:
        """分类：successful_call, failure, prompt_injection_attempt, data_exfiltration, accurate_tool_choice, wrong_tool_choice"""
    def score(self, agent_id) -> ReputationScore: ...
    def all_scores(self) -> list[ReputationScore]: ...
```

**任务 1.3：创建信任策略 + 可验证凭证**

文件：
- 创建 `chainforge/enterprise/identity/trust.py`
- 创建 `chainforge/enterprise/identity/credential.py`

```python
# trust.py
class TrustRule(BaseModel):
    min_reputation: int | None
    max_reputation: int | None
    action: str   # "allow" | "block_all_tools" | "restrict"
    allowed_tools: list[str] = []
    blocked_tools: list[str] = []
    reason: str = ""

class TrustPolicy(BaseModel):
    rules: list[TrustRule]
    def evaluate(self, reputation_score) -> TrustDecision: ...

# credential.py
class VerifiableCredential(BaseModel):
    issuer_id: str; subject_id: str
    claims: dict; issued_at: float; expires_at: float
    signature: str  # issuer 对 claims+timestamps 的签名
    @classmethod
    def issue(cls, issuer, subject_id, claims, expires_in_days) -> "VerifiableCredential": ...
    def verify(self, issuer_public_key: str) -> bool:
        """检查签名和过期。"""
```

**任务 1.4：验证**

```bash
python -c "
from chainforge.enterprise.identity import AgentIdentity, ReputationEngine, TrustPolicy, VerifiableCredential

# 密钥生成 + 签名
id_a = AgentIdentity.create('test-agent', 'acme', ['chat'])
sig = id_a.sign(b'hello')
assert AgentIdentity.verify(b'hello', sig, id_a.public_key)
assert not AgentIdentity.verify(b'wrong', sig, id_a.public_key)
assert id_a.did.startswith('did:chainforge:')

# 信誉
e = ReputationEngine()
e.record_event(id_a.agent_id, 'successful_call', latency_ms=100)
s = e.score(id_a.agent_id)
assert s.overall >= 80  # 少量正向事件，无负面事件

# 凭证
vc = VerifiableCredential.issue(id_a, 'subject-1', {'role': 'admin'}, 30)
assert vc.verify(id_a.public_key)

print('OK')
"
```

提交：`feat: Phase 30-1 — Agent Identity & Reputation Protocol`

---

## 阶段二：Agent 经济协议

理由：Economy 使用 Identity 进行交易签名。当 buyer 发送请求时，seller 使用 Identity 验证请求来源。所有交易在 CreditLedger 中排列，通过定价合约计费，并通过 BillingContract 为计费中间件提供数据源。

**任务 2.1：创建经济引擎 + CreditLedger + BillingContract + Invoice**

文件：
- 创建 `chainforge/enterprise/economy/__init__.py`
- 创建 `chainforge/enterprise/economy/engine.py` — AgentEconomy
- 创建 `chainforge/enterprise/economy/ledger.py` — CreditLedger
- 创建 `chainforge/enterprise/economy/contract.py` — BillingContract + Transaction
- 创建 `chainforge/enterprise/economy/invoice.py` — Invoice + RevenueReport
- 创建 `chainforge/enterprise/economy/middleware.py` — 自动计费中间件

核心类：
```python
class Transaction(BaseModel):
    id: str; from_agent_id: str; to_agent_id: str
    tool_name: str; pricing_model: str  # per_tool_call|per_token|per_request
    unit_price: float; quantity: int; total_amount: float
    timestamp: float; settled: bool = False

class BillingContract(BaseModel):
    pricing: dict[str, float]   # {"per_tool_call": 0.05}
    free_quota: int = 0          # 每日免费配额
    require_approval_above: float | None = None

class CreditLedger:
    def record(self, tx: Transaction): ...
    def balance(self, agent_id) -> float: ...
    def outstanding(self, agent_id) -> list[Transaction]: ...
    def settle(self, tx_ids) -> list[Transaction]: ...

class AgentEconomy:
    def __init__(self, settlement_currency="usd"): ...
    def invoice(self, agent_id, period) -> Invoice: ...
    def revenue(self, agent_id, period) -> RevenueReport: ...
    def settle(self, from_agent, to_agent, amount, method): ...
    def middleware(self, billing_contract, role) -> Callable: ...
```

**任务 2.2：验证**

```bash
python -c "
from chainforge.enterprise.economy import AgentEconomy, BillingContract

e = AgentEconomy()
contract = BillingContract(pricing={'per_tool_call': 0.05})
inv = e.invoice('buyer-1', period='today')
assert inv.total_payable == 0.0
print('OK')
"
```

提交：`feat: Phase 30-2 — Agent Economic Protocol`

---

## 阶段三：Agent 能力注册中心

理由：Registry 使用 Identity 进行注册验证和签名。Agent 注册时提供经过签名的身份，支持跨组织信任场景。语义发现使用关键词匹配（生产版升级至向量搜索）。

**任务 3.1：创建 AgentProfile + CapabilityRegistry + AutoNegotiation**

文件：
- 创建 `chainforge/enterprise/registry/__init__.py`
- 创建 `chainforge/enterprise/registry/profile.py` — AgentProfile + SLA
- 创建 `chainforge/enterprise/registry/registry.py` — CapabilityRegistry
- 创建 `chainforge/enterprise/registry/discovery.py` — CapabilityQuery + 语义匹配
- 创建 `chainforge/enterprise/registry/negotiation.py` — AutoNegotiation

核心类：
```python
class ServiceLevelAgreement(BaseModel):
    max_latency_ms: int = 500
    availability: float = 0.99

class AgentProfile(BaseModel):
    agent_id: str; name: str; version: str
    capabilities: list[str]          # 能力标签，如 "postgresql:query"
    tools_exposed: list[str]
    endpoints: dict[str, str]        # {"a2a": "...", "http": "..."}
    health_check_url: str
    pricing: dict[str, float]        # {"per_query": 0.001}
    constraints: dict[str, Any]      # {"max_concurrent": 10}
    sla: ServiceLevelAgreement
    supersedes: list[str] = []       # 替换哪些旧版本

class CapabilityRegistry:
    def __init__(self, backend="sqlite", namespace="default"): ...
    async def register(self, profile): ...
    async def discover(self, capability=None, query=None, **filters) -> list[tuple[AgentProfile, float]]:
        """返回 (profile, relevance_score) 列表。"""
    async def unregister(self, agent_id): ...
    async def deprecate(self, agent_id, version, sunset_date): ...
    async def health_check(self, agent_id) -> bool: ...

class AutoNegotiation:
    def __init__(self, requester, capability_needed, constraints): ...
    async def start(self) -> NegotiationResult: ...
```

**任务 3.2：验证**

```bash
python -c "
import asyncio
from chainforge.enterprise.registry import CapabilityRegistry, AgentProfile

async def main():
    r = CapabilityRegistry(backend='sqlite', namespace='test')
    profile = AgentProfile(agent_id='a1', name='Test', version='1.0',
        capabilities=['db:query'], tools_exposed=['query'], endpoints={},
        health_check_url='http://localhost', pricing={},
        sla=None)
    r.register(profile)
    matches = await r.discover(capability='db:query')
    assert len(matches) == 1
    print('OK')

asyncio.run(main())
"
```

提交：`feat: Phase 30-3 — Agent Capability Registry`

---

## 阶段四：持久化 Agent 执行

理由：DurableExecutor 构建在 CyclicGraph + Checkpointer（已有）之上。Checkpoint 保存 LLM 消息、状态快照和累积成本。崩溃恢复从最新的 checkpoint 重新开始。

**任务 4.1：创建 DurableExecutor + JobHandle + Checkpoint + DeadLetterQueue + ExecutionJournal**

文件：
- 创建 `chainforge/enterprise/durable/__init__.py`
- 创建 `chainforge/enterprise/durable/executor.py` — DurableExecutor
- 创建 `chainforge/enterprise/durable/handle.py` — JobHandle + JobStatus
- 创建 `chainforge/enterprise/durable/checkpoint.py` — Checkpoint 模型和持久化
- 创建 `chainforge/enterprise/durable/dlq.py` — DeadLetterQueue
- 创建 `chainforge/enterprise/durable/journal.py` — ExecutionJournal
- 创建 `chainforge/enterprise/durable/recovery.py` — CrashRecoveryPolicy

核心类：
```python
class Checkpoint(BaseModel):
    id: str; job_id: str; step_index: int; total_steps: int
    messages_json: str             # serialized Message list
    state_snapshot: dict           # CyclicGraph node position
    tokens_used: int; cost_accumulated: float
    tool_results_cached: dict; timestamp: float

class JobHandle(BaseModel):
    job_id: str; agent_id: str
    status: str   # queued|running|checkpointing|done|failed|cancelled
    progress: float; created_at: float; started_at: float | None
    last_checkpoint_at: float | None; result: Any | None; error: str | None

class DurableExecutor:
    def __init__(self, backend="sqlite", checkpoint_every=30, crash_recovery=None,
                 on_complete=None, on_failure=None, on_progress=None): ...
    async def run_sync(self, agent, prompt, **opts) -> Any:
        """Run，带 checkpoint。崩溃后可以从最后一个 checkpoint 恢复。"""
    async def submit(self, agent, prompt, **opts) -> JobHandle: ...
    async def status(self, job_id) -> JobStatus: ...
    async def wait(self, job_id, timeout=None) -> Any: ...
    async def cancel(self, job_id) -> bool: ...
    async def resume(self, job_id) -> JobHandle: ...

class DeadLetterQueue:
    def __init__(self, backend="sqlite"): ...
    def enqueue(self, job_id, step, reason, context): ...
    def list(self) -> list[DLQItem]: ...
    def retry(self, job_id) -> bool: ...
    def discard(self, job_id) -> bool: ...

class ExecutionJournal:
    def __init__(self, backend="sqlite"): ...
    def record(self, job_id, step, event_type, detail): ...
    def trace(self, job_id) -> list[JournaLstep]: ...
    def cost_at_checkpoint(self, checkpoint_id) -> float: ...
```

**任务 4.2：验证**

```bash
python -c "
from chainforge.enterprise.durable import DurableExecutor, JobHandle, Checkpoint

executor = DurableExecutor(backend='sqlite')
# 没有实际 LLM 的冒烟测试
handle = JobHandle(job_id='test-1', agent_id='a1', status='queued', progress=0.0, created_at=0)
assert handle.job_id == 'test-1'
print('OK')
"
```

提交：`feat: Phase 30-4 — Durable Agent Execution`

---

## 阶段五：Agent 数据血缘与 GDPR Right-to-Forget

理由：Lineage tracker 使用中间件拦截所有 LLM 调用和工具执行，记录数据主体和存储位置。通过 ErasureRequest 提供一键删除，通过 DeletionProof 提供防篡改的删除证明。

**任务 5.1：创建 DataLineageTracker + ErasureRequest + DeletionProof**

文件：
- 创建 `chainforge/enterprise/lineage/__init__.py`
- 创建 `chainforge/enterprise/lineage/tracker.py` — DataLineageTracker + 中间件
- 创建 `chainforge/enterprise/lineage/query.py` — DataSubject + DataFootprint
- 创建 `chainforge/enterprise/lineage/erasure.py` — ErasureRequest + ErasureReport + 处理器注册
- 创建 `chainforge/enterprise/lineage/proof.py` — DeletionProof

核心类：
```python
class DataSubject(BaseModel):
    user_id: str | None; email: str | None; phone: str | None; ip_address: str | None

class DataLocation(BaseModel):
    type: str            # llm_response|tool_result|vector_memory|cache|s3_object
    provider: str        # openai|qdrant|postgres|s3
    identifier: str      # 唯一标识
    content_type: str    # pii|partial_pii|derived|metadata
    deletable: bool
    deletion_method: str # api_delete|db_delete|anonymize|ttl_wait

class DataFootprint(BaseModel):
    subject: DataSubject
    locations: list[DataLocation]
    total_locations: int
    risk_assessment: str
    def to_json(self): ...

class DataLineageTracker:
    def __init__(self, backend="sqlite"): ...
    def middleware(self) -> Callable: ...
    def query(self, q: LineageQuery) -> DataFootprint: ...
    async def erase(self, request: ErasureRequest) -> ErasureReport: ...
    def register_handler(self, location_type, handler): ...

class ErasureRequest(BaseModel):
    data_subjects: list[DataSubject]
    reason: str; requested_by: str; deadline_hours: int = 72

class ErasureReport(BaseModel):
    request_id: str; status: str   # complete|partial|failed
    items: list[dict]; completed_items: int; pending_items: int
    def to_json(self): ...

class DeletionProof:
    def __init__(self, report: ErasureReport): ...
    def export(self, path: str): ...    # → JSON，带签名
    def verify(self) -> bool: ...
```

**任务 5.2：验证**

```bash
python -c "
from chainforge.enterprise.lineage import DataLineageTracker, DataSubject, ErasureRequest

tracker = DataLineageTracker(backend='sqlite')
ds = DataSubject(email='test@example.com')
footprint = tracker.query(ds)
assert footprint.total_locations >= 0
print('OK')
"
```

提交：`feat: Phase 30-5 — Agent Data Lineage & GDPR Right-to-Forget`

---

## 最终验证

```bash
cd /Users/carlos/AiProject/ChainForge && .venv/bin/python -c "
from chainforge.enterprise.identity import AgentIdentity, ReputationEngine, TrustPolicy, VerifiableCredential
from chainforge.enterprise.economy import AgentEconomy, BillingContract
from chainforge.enterprise.registry import CapabilityRegistry, AgentProfile
from chainforge.enterprise.durable import DurableExecutor, JobHandle, DeadLetterQueue
from chainforge.enterprise.lineage import DataLineageTracker, DataSubject, ErasureRequest
print('All 5 modules import and smoke test passed')
"
```

---

## 交付物汇总

| 阶段 | 模块 | 文件数 | 约代码行数 |
|------|------|--------|-----------|
| 1 | 身份与信誉 | 5 | ~550 |
| 2 | 经济协议 | 5 | ~450 |
| 3 | 能力注册中心 | 5 | ~550 |
| 4 | 持久化执行 | 6 | ~600 |
| 5 | 数据血缘 / GDPR | 4 | ~450 |
| **总计** | **5 个模块** | **~25 个文件** | **~2,600 行** |

---

## 实施顺序

```
身份 → 经济 → 注册中心 → 持久化 → 数据血缘
```
