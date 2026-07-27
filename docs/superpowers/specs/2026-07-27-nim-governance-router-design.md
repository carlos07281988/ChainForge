# ChainForge × NVIDIA NIM — 三阶段优化设计

**日期：** 2026-07-27
**状态：** 已批准
**范围：** NVIDIA NIM Provider、Governance 2.0、SmartRouter 3.0

---

## 背景

参考 LangChain + NVIDIA NIM 架构模式：
```
用户请求 → Agent 编排 → NVIDIA NIM 推理微服务 → 工具集 → 安全治理层 → 执行结果
```

ChainForge 在编排、工具、执行三个维度已超越参考架构，但在以下三方面存在缺口：
1. **NVIDIA NIM 推理** — 无私有化 GPU 推理 Provider
2. **治理层深度** — guardrails/tracing/provenance 各自为政，缺乏统一策略引擎
3. **路由感知** — 无法基于数据敏感度/基础设施可用性做路由决策

---

## 总体架构

```
用户请求
   │
   ▼
┌─────────────────────────────────────────────────────┐
│              SmartRouter 3.0 (Phase C)               │
│  数据分类 → 策略匹配 → 基础设施感知 → 模型选择         │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    云端 API      本地 NIM      Ollama/Bedrock
    (OpenAI等)   (Phase A)      (已有)
          │            │            │
          └────────────┼────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│            Governance 2.0 (Phase B)                  │
│  策略引擎 → 数据驻留 → 版本锁定 → 审计报告            │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
                   执行结果
```

---

## Phase A：NVIDIA NIM Provider

### 动机

NVIDIA NIM 暴露 OpenAI 兼容 API (`/v1`)，可直接用 `openai` 库调用。但 NIM 的运维模型（本地 GPU 服务、健康检查、模型热加载）与云端 API 完全不同，需独立 Provider。

### 设计决策

- **不复用 `OpenAIProvider`** — 运维模式不同（本地 GPU vs 云端 API），继承会破坏单一职责
- **不创建独立 HealthChecker 类** — `health_check()` 和 `list_models()` 作为 Provider 方法足够，避免文件碎片
- **在 `adaptiverouter._create_provider` 加入 `"nim"` 分支** — 让路由层能统一调度 NIM

### 文件

**`chainforge/providers/nim.py`**

```python
class NIMProvider(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    model: str                          # e.g. meta/llama-3.1-70b-instruct
    base_url: str = "http://localhost:8000/v1"
    api_key: str | None = None          # NIM 默认不需要 auth
    
    # 本地 GPU 特性
    health_check_interval: int = 30
    _last_health: bool = True
    _available_models: list[str] = []

    @property
    def capabilities(self) -> set[str]: ...
    
    async def health_check(self) -> bool:
        """GET /v1/models → 验证服务存活"""
    
    async def list_models(self) -> list[str]:
        """列出此 NIM 实例所有可用模型"""
    
    async def generate(self, messages, tools, **kwargs) -> LLMResponse:
        """标准生成，透传 NIM 特有参数"""
    
    async def stream_generate(self, messages, tools, **kwargs) -> AsyncIterator:
        """SSE 流式，与 OpenAI 协议完全兼容"""
```

### 集成点

| 位置 | 改动 |
|------|------|
| `providers/__init__.py` | 加入 `"NIMProvider"` 到 lazy registry |
| `routing/adaptive.py` | `_create_provider` 加入 `"nim"` 分支 |
| `core/llm.py` | `MODEL_PRICING` 加入常见 NIM 模型 |

### 交付物

- `chainforge/providers/nim.py`（新文件，~180 行）
- 无 breaking changes

---

## Phase B：Governance 2.0

### 动机

现有能力：
- `guardrails/` — 输入/输出安全检测 + 中间件集成 ✅
- `tracing/` — span/trace 监控 ✅
- `core/provenance.py` — 因果追踪 ✅

问题：三者独立工作，没有统一策略引擎把它们串起来。企业级治理需要：**谁 → 用什么数据 → 走什么模型 → 在哪执行 → 留什么审计**。

### 设计决策

- **不替换现有 guardrails** — 它们继续做检测，Governance 2.0 在其之上
- **`GovernancePolicy` 是声明式规则** — 不做实时检测，只做策略路由
- **`AuditReporter` 消费已有数据** — 从 `ProvenanceTracker` + `Tracer` 读取，不重复采集
- **不与 SmartRouter 3.0 耦合** — PolicyEngine 独立可用，Router 通过组合使用它

### 文件结构

```
chainforge/governance/        # 新包
├── __init__.py
├── policy.py                 # GovernancePolicy, PolicyEngine
├── residency.py              # DataResidency — 数据驻留控制
├── versioning.py             # ModelVersionTracker — 版本锁定
└── audit.py                  # AuditReporter — 合规审计报告
```

### 核心组件

```python
# policy.py
class GovernancePolicy(BaseModel):
    """声明式治理规则"""
    name: str
    data_labels: list[str] = []       # 触发标签: "pii", "internal", "public"
    model_provider: str | None = None # 强制 provider: "nim", "ollama"
    region: str | None = None         # 数据驻留区域
    version_pin: str | None = None    # 模型版本锁定
    action: str = "enforce"           # enforce | audit_only | warn

class PolicyEngine:
    policies: list[GovernancePolicy]
    
    async def evaluate(self, labels: list[str], context: dict) -> PolicyDecision:
        """评估所有策略 → 返回合规决策（允许/拒绝/审计）"""

# residency.py
class DataResidency:
    """根据数据标签确定允许的 provider 列表"""
    RULES = {
        "pii":      ["nim", "ollama"],     # 敏感数据 → 仅本地
        "internal": ["nim", "ollama"],
        "public":   ["openai", "anthropic", "google", "nim", ...],  # 全部
    }

# versioning.py
class ModelVersionTracker:
    """记录模型版本 + 参数快照 → 每次调用可复现"""
    async def snapshot(self, provider, model, params) -> VersionRecord: ...
    async def verify(self, provider, expected_version) -> bool: ...

# audit.py
class AuditReporter:
    """消费 ProvenanceTracker + Tracer → 生成审计报告"""
    def __init__(self, provenance, tracer): ...
    def generate_report(self, time_range) -> AuditReport: ...
    def compliance_check(self, policies) -> list[ComplianceItem]: ...
```

### 集成点

| 位置 | 改动 |
|------|------|
| `guardrails/middleware.py` | `GuardrailMiddleware.__init__` 加 `policy_engine` 参数 |
| `core/agent.py` | `Agent` 加 `governance_policy` 参数（可选，向后兼容）|

### 交付物

- 4 个新文件，~350 行
- 无 breaking changes（全部可选参数）

---

## Phase C：SmartRouter 3.0 — 策略感知路由

### 动机

现有 `AdaptiveRouter`（成本/能力/延迟路由）+ `SmartRouter`（复杂度分类路由）已工作良好。3.0 需要在此基础上感知：
1. **数据敏感度** — 敏感数据必须走本地模型
2. **基础设施状态** — GPU 是否在线、NIM 是否健康
3. **治理策略** — 版本锁定、区域限制

### 设计决策

- **包装现有 `AdaptiveRouter`，不改其内部** — 策略层是独立过滤器
- **`InfraProbe` 做轻量探针** — 不引入外部依赖，用 aiohttp/httpx 发健康检查
- **`DataClassifier` 做正则+关键词快速分类** — 不额外调 LLM，不增加延迟

### 文件

**`chainforge/routing/policy_router.py`**

```python
class InfraProbe:
    """基础设施探针 — 检测本地模型实时可用性"""
    async def probe_nim(self, base_url: str) -> bool: ...
    async def probe_ollama(self) -> bool: ...
    @property
    def available_backends(self) -> set[str]: ...

class DataClassifier:
    """轻量数据分类 — 正则+关键词，不调 LLM"""
    def classify(self, text: str) -> list[str]:
        # → ["pii"] or ["internal"] or ["public"]

class PolicyAwareRouter:
    """组合 AdaptiveRouter + PolicyEngine + InfraProbe"""
    
    def __init__(self, registry, policy_engine, infra_probe):
        self._adaptive = AdaptiveRouter(registry)
        self._policy = policy_engine
        self._infra = infra_probe
        self._classifier = DataClassifier()
    
    async def select(self, prompt, context=None) -> LLM:
        # 1. 分类数据 → labels
        # 2. 评估策略 → 允许的 provider 列表
        # 3. 过滤基础设施 → 实际在线的后端
        # 4. 在合格候选内 → AdaptiveRouter 做成本/能力优化
```

### 集成点

| 位置 | 改动 |
|------|------|
| `routing/__init__.py` | 导出 `PolicyAwareRouter` |

### 交付物

- `chainforge/routing/policy_router.py`（新文件，~200 行）
- 无 breaking changes

---

## 实施顺序

```
Phase A (1 新文件, ~180 行)  →  独立可交付
Phase B (4 新文件, ~350 行)  →  依赖 Phase A（registry 中有 nim）
Phase C (1 新文件, ~200 行)  →  依赖 Phase A + B
```

---

## 验收标准

### Phase A
- [ ] `NIMProvider` 可从本地 NIM 实例获取模型列表
- [ ] `generate()` 和 `stream_generate()` 正常工作
- [ ] 健康检查失败时自动标记 `_last_health = False`
- [ ] `Agent(llm=NIMProvider(...))` 可运行

### Phase B
- [ ] `GovernancePolicy` 声明规则 → `PolicyEngine` 正确评估
- [ ] `DataResidency` 对 PII 数据只允许本地 provider
- [ ] `ModelVersionTracker` 记录并可验证模型版本
- [ ] `AuditReporter` 生成可读审计报告

### Phase C
- [ ] 输入含 PII → 自动路由到本地 NIM（即使云端 API 更便宜）
- [ ] NIM 不可用时 → 自动回退到 Ollama（策略允许的前提下）
- [ ] 公开数据 → 按成本优化正常路由
- [ ] 不会因分类器误判导致敏感数据走云端
