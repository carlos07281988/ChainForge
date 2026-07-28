# Enterprise Fabric 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 为 ChainForge 添加四个企业级模块 — Economics Layer、EU AI Act Compliance、Supply Chain Security、Collective Agent Memory

**Architecture:** `chainforge/enterprise/` 新包，四个独立子模块，纯 SDK（零前端）。每模块通过 middleware 集成 Agent，全部可选。

**Tech Stack:** Python 3.11+, Pydantic, sqlite3, httpx

## 全局约束

- `from __future__ import annotations` 在所有新文件
- Apache 2.0 license header
- Pydantic model 使用 `ConfigDict(arbitrary_types_allowed=True)`
- **纯 SDK，零前端 UI** — 所有数据通过 `.to_json()` / `.to_dict()` 导出
- **Middleware 集成 Agent** — 不修改 Agent 核心 API
- **Lazy import** — `chainforge/enterprise/__init__.py` 不导入子模块
- 每个模块独立可测试，无强制依赖
- 实施顺序: Compliance → Economics → Collective → Supply Chain

---

## Phase 1: Compliance Engine (Module 2)

### Task 1.1: RiskClassifier + RiskRule

**Files:**
- Create: `chainforge/enterprise/__init__.py`
- Create: `chainforge/enterprise/compliance/__init__.py`
- Create: `chainforge/enterprise/compliance/classifier.py`

**Step 1 — Create `chainforge/enterprise/__init__.py`:**

```python
# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""ChainForge Enterprise — governance, economics, security, and collective intelligence.

Each submodule is lazily imported. Import what you need:
    from chainforge.enterprise.economics import CostTracker
    from chainforge.enterprise.compliance import ComplianceGuard
    from chainforge.enterprise.collective import CollectiveMemory
    from chainforge.enterprise.supply_chain import SupplyChainScanner
"""
```

**Step 2 — Create `chainforge/enterprise/compliance/__init__.py`:**

```python
# Copyright 2026 ChainForge Contributors. Apache 2.0.
from chainforge.enterprise.compliance.classifier import RiskClassifier, RiskRule
from chainforge.enterprise.compliance.guard import ComplianceGuard
from chainforge.enterprise.compliance.auditor import ComplianceAuditor, ComplianceReport
from chainforge.enterprise.compliance.hitl import HITLPolicy, ApprovalRequest
__all__ = ["RiskClassifier","RiskRule","ComplianceGuard","ComplianceAuditor","ComplianceReport","HITLPolicy","ApprovalRequest"]
```

**Step 3 — Create `chainforge/enterprise/compliance/classifier.py`:**

```python
# Apache 2.0
"""RiskClassifier — classify agent risk tier for EU AI Act compliance."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class RiskTier(str, Enum):
    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"

class RiskRule(BaseModel):
    """A single rule for risk classification."""
    tool_contains: str | None = None
    data_labels: list[str] | None = None
    provider_cloud: bool | None = None  # True = cloud provider triggers
    domain: str | None = None
    risk: RiskTier = RiskTier.MINIMAL
    reason: str = ""

_BUILTIN_RULES: list[RiskRule] = [
    RiskRule(tool_contains="delete", risk=RiskTier.HIGH, reason="Tool can delete data permanently"),
    RiskRule(tool_contains="write_file", risk=RiskTier.HIGH, reason="Tool can write to filesystem"),
    RiskRule(tool_contains="send_email", risk=RiskTier.LIMITED, reason="Tool can send external communications"),
    RiskRule(data_labels=["pii"], provider_cloud=True, risk=RiskTier.HIGH, reason="PII sent to cloud provider"),
    RiskRule(domain="healthcare", risk=RiskTier.HIGH, reason="Healthcare decisions affect human wellbeing"),
    RiskRule(domain="legal", risk=RiskTier.LIMITED, reason="Legal advice requires oversight"),
    RiskRule(domain="finance", risk=RiskTier.LIMITED, reason="Financial decisions require oversight"),
]

class RiskClassifier:
    """Classify an agent's risk tier based on its tools, data, and domain."""
    def __init__(self, rules: list[RiskRule] | None = None):
        self._rules = list(_BUILTIN_RULES)
        if rules:
            self._rules.extend(rules)

    @property
    def rules(self) -> list[RiskRule]: return list(self._rules)

    def classify(self, tools: list[str], data_labels: list[str] | None = None, domain: str | None = None) -> tuple[RiskTier, list[RiskRule]]:
        """Return (highest_risk_tier, triggering_rules)."""
        labels = data_labels or []
        matched: list[RiskRule] = []
        highest = RiskTier.MINIMAL
        tier_order = {RiskTier.UNACCEPTABLE: 4, RiskTier.HIGH: 3, RiskTier.LIMITED: 2, RiskTier.MINIMAL: 1}
        for rule in self._rules:
            if rule.tool_contains and any(rule.tool_contains in t for t in tools):
                matched.append(rule)
            elif rule.data_labels and rule.provider_cloud is True and any(l in labels for l in rule.data_labels):
                matched.append(rule)
            elif rule.domain and domain and rule.domain in domain.lower():
                matched.append(rule)
        for r in matched:
            if tier_order[r.risk] > tier_order[highest]:
                highest = r.risk
        return highest, matched
```

### Task 1.2: HITLPolicy + ApprovalRequest

**Files:**
- Create: `chainforge/enterprise/compliance/hitl.py`

```python
# Apache 2.0
"""HITLPolicy — human-in-the-loop enforcement for high-risk agent actions."""
from __future__ import annotations
from collections.abc import Callable, Awaitable
from typing import Any
from pydantic import BaseModel, Field
from chainforge.enterprise.compliance.classifier import RiskTier

class ApprovalRequest(BaseModel):
    """An approval request sent to a human reviewer."""
    request_id: str
    agent_name: str
    action: str
    risk_tier: RiskTier
    reason: str
    context: dict[str, Any] = Field(default_factory=dict)

ApprovalHandler = Callable[[ApprovalRequest], Awaitable[bool]]

class HITLPolicy(BaseModel):
    """Policy for when human approval is required."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    require_approval_on: list[RiskTier] = Field(default_factory=lambda: [RiskTier.HIGH])
    approval_handler: ApprovalHandler | None = None

    def needs_approval(self, tier: RiskTier) -> bool:
        return tier in self.require_approval_on
```

### Task 1.3: ComplianceAuditor + ComplianceReport

**Files:**
- Create: `chainforge/enterprise/compliance/auditor.py`

```python
# Apache 2.0
"""ComplianceAuditor — generates EU AI Act compliance reports."""
from __future__ import annotations
import json, time, sqlite3
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

class ComplianceCheck(BaseModel):
    article: int
    requirement: str
    status: str = "compliant"  # compliant | non_compliant | not_applicable
    detail: str = ""

class ComplianceReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"compliance-{int(time.time())}")
    generated_at: float = Field(default_factory=time.time)
    risk_tier: str = "minimal"
    checks: list[ComplianceCheck] = Field(default_factory=list)
    total_events: int = 0
    recommendations: list[str] = Field(default_factory=list)
    @property
    def compliance_score(self) -> float:
        if not self.checks: return 1.0
        return sum(1 for c in self.checks if c.status == "compliant") / len(self.checks)
    def to_json(self) -> dict[str, Any]: return self.model_dump()
    def to_markdown(self) -> str:
        lines = [f"# Compliance Report: {self.report_id}", f"Risk Tier: **{self.risk_tier}**", f"Score: {self.compliance_score:.0%}", ""]
        for c in self.checks:
            icon = "✅" if c.status == "compliant" else "❌"
            lines.append(f"- {icon} Art.{c.article}: {c.requirement} — {c.detail}")
        if self.recommendations:
            lines.append("\n## Recommendations")
            for r in self.recommendations: lines.append(f"- {r}")
        return "\n".join(lines)

_EU_AI_ACT_ARTICLES = [
    (11, "Technical documentation", "Agent must have documented purpose, design, and limitations"),
    (12, "Record-keeping", "All agent actions must be logged for audit"),
    (13, "Transparency", "Users must be informed they are interacting with an AI agent"),
    (14, "Human oversight", "High-risk agents must have human-in-the-loop capability"),
    (15, "Accuracy and robustness", "Agent must handle errors gracefully and not produce harmful outputs"),
]

class ComplianceAuditor:
    """Records compliance events and generates audit reports."""
    def __init__(self, log_path: str = "compliance.db", regulation: str = "eu-ai-act-2026"):
        self._log_path = Path(log_path)
        self._regulation = regulation
        self._conn: sqlite3.Connection | None = None
        self._init_db()
    def _init_db(self):
        self._conn = sqlite3.connect(str(self._log_path))
        self._conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, event_type TEXT, data TEXT)")
        self._conn.commit()
    def record(self, event_type: str, data: dict[str, Any]) -> None:
        if self._conn:
            self._conn.execute("INSERT INTO events (timestamp, event_type, data) VALUES (?, ?, ?)", (time.time(), event_type, json.dumps(data)))
            self._conn.commit()
    def generate(self, risk_tier: str = "minimal", has_hitl: bool = False) -> ComplianceReport:
        count = 0
        if self._conn:
            cur = self._conn.execute("SELECT COUNT(*) FROM events")
            count = cur.fetchone()[0]
        checks = []
        for art_num, name, detail in _EU_AI_ACT_ARTICLES:
            status = "compliant"
            detail_msg = detail
            if art_num == 12 and count == 0: status = "non_compliant"; detail_msg = "No audit events recorded"
            if art_num == 14 and not has_hitl: status = "non_compliant"; detail_msg = "HITL not configured"
            checks.append(ComplianceCheck(article=art_num, requirement=name, status=status, detail=detail_msg))
        recs = [c.detail for c in checks if c.status == "non_compliant"]
        return ComplianceReport(risk_tier=risk_tier, checks=checks, total_events=count, recommendations=recs)
    def close(self):
        if self._conn: self._conn.close()
```

### Task 1.4: ComplianceGuard middleware

**Files:**
- Create: `chainforge/enterprise/compliance/guard.py`

```python
# Apache 2.0
"""ComplianceGuard — middleware that enforces EU AI Act compliance."""
from __future__ import annotations
from collections.abc import AsyncIterator
from typing import Any
from chainforge.core.message import Message, Role
from chainforge.core.stream import EventType, StreamEvent
from chainforge.enterprise.compliance.classifier import RiskClassifier, RiskTier
from chainforge.enterprise.compliance.hitl import HITLPolicy, ApprovalRequest
from chainforge.enterprise.compliance.auditor import ComplianceAuditor
from chainforge.logging import get_logger
logger = get_logger("enterprise.compliance")

class ComplianceGuard:
    """Middleware: classify risk on first user message, require HITL if high risk."""
    def __init__(self, classifier: RiskClassifier | None = None, hitl_policy: HITLPolicy | None = None, auditor: ComplianceAuditor | None = None):
        self._classifier = classifier or RiskClassifier()
        self._hitl = hitl_policy or HITLPolicy()
        self._auditor = auditor
        self._risk_tier: RiskTier | None = None
        self._agent_name: str = "unknown"

    async def __call__(self, messages: list[Message], ctx: dict[str, Any], next_handler) -> AsyncIterator[StreamEvent]:
        # Classify on first pass
        if self._risk_tier is None:
            tools = [t.name for t in ctx.get("tools", [])]
            labels = ctx.get("data_labels", [])
            domain = ctx.get("domain")
            self._risk_tier, matched = self._classifier.classify(tools, labels, domain)
            self._agent_name = ctx.get("agent_name", "unknown")
            logger.info(f"Compliance: risk={self._risk_tier.value}, triggers={[r.reason for r in matched]}")
            if self._auditor:
                self._auditor.record("risk_classification", {"risk_tier": self._risk_tier.value, "triggers": [r.reason for r in matched]})

        # HITL gate
        if self._hitl.needs_approval(self._risk_tier):
            last_msg = messages[-1].content if messages else ""
            req = ApprovalRequest(request_id=f"hitl-{ctx.get('run_id','')}", agent_name=self._agent_name, action=str(last_msg)[:200], risk_tier=self._risk_tier, reason=f"Risk tier: {self._risk_tier.value}")
            if self._auditor: self._auditor.record("hitl_required", req.model_dump())
            if self._hitl.approval_handler:
                approved = await self._hitl.approval_handler(req)
                if not approved:
                    yield StreamEvent(type=EventType.ERROR, content="Human approval denied", metadata={"reason": "hitl_denied"})
                    return
                if self._auditor: self._auditor.record("hitl_approved", {"request_id": req.request_id})
            else:
                logger.warning(f"HITL required but no approval_handler configured. Blocking.")
                yield StreamEvent(type=EventType.ERROR, content="Human approval required but no handler configured", metadata={"reason": "hitl_no_handler"})
                return

        async for event in next_handler(messages, ctx):
            yield event
```

**Step 5 — Verify Task 1.1-1.4:**

```bash
python -c "
from chainforge.enterprise.compliance import RiskClassifier, RiskRule, RiskTier, ComplianceAuditor, ComplianceReport
c = RiskClassifier()
tier, rules = c.classify(['delete_file'], [], None)
assert tier == RiskTier.HIGH
tier2, _ = c.classify(['query_db'], [], 'healthcare')
assert tier2 == RiskTier.HIGH
auditor = ComplianceAuditor(log_path=':memory:')
auditor.record('test', {})
report = auditor.generate(risk_tier='limited', has_hitl=True)
assert report.compliance_score >= 0.8
md = report.to_markdown()
assert '# Compliance Report' in md
auditor.close()
print('OK')
"
```

Commit: `feat: Phase 1 — EU AI Act Compliance Engine`

---

## Phase 2: Agent Economics Layer (Module 1)

### Task 2.1: CostTracker + TokenLedger + CostReport

**Files:**
- Create: `chainforge/enterprise/economics/__init__.py`
- Create: `chainforge/enterprise/economics/ledger.py`
- Create: `chainforge/enterprise/economics/tracker.py`
- Create: `chainforge/enterprise/economics/report.py`

**For brevity, key class signatures (full code in dispatch):**

`ledger.py` — `TokenLedger(backend="sqlite"|"memory")` with `.record(CostRecord)`, `.query(group_by, period) -> list[dict]`

`tracker.py`:
```python
class CostTracker:
    """Records LLM cost automatically."""
    def __init__(self, backend="memory", db_path=None): ...
    def middleware(self, attribution: dict[str,str]) -> Callable:
        """Returns a middleware that records costs from LLMResponse."""
        async def _mw(messages, ctx, next_handler):
            start = time.time()
            async for event in next_handler(messages, ctx):
                if isinstance(event, LLMResponse) and event.usage:
                    record = CostRecord(timestamp=time.time(), model=event.model, provider=ctx.get("provider","unknown"),
                        input_tokens=event.usage.get("prompt_tokens",0), output_tokens=event.usage.get("completion_tokens",0),
                        cost=event.cost or 0.0, duration_ms=(time.time()-start)*1000, attribution=attribution)
                    self._ledger.record(record)
                yield event
        return _mw
    def report(self, group_by="model", period=None) -> CostReport: ...
    def optimize(self, period="last-30-days") -> CostOptimization: ...
```

`report.py` — `CostReport(total, rows, period, group_by)`, `.to_json() -> list[dict]`, `CostOptimization(potential_savings, items)`

### Task 2.2: BudgetGuard middleware

**Files:**
- Create: `chainforge/enterprise/economics/guard.py`

```python
class BudgetGuard:
    """Middleware: enforce daily budget. On limit: downgrade, block, or warn."""
    def __init__(self, daily_limit: float, on_limit="downgrade", fallback_model=None, tracker=None): ...
    async def __call__(self, messages, ctx, next_handler) -> AsyncIterator[StreamEvent]:
        today_spend = self._tracker.report(period="today").total if self._tracker else 0.0
        if today_spend >= self._daily_limit:
            if self._on_limit == "downgrade" and self._fallback_model:
                ctx["llm_override"] = self._fallback_model
            elif self._on_limit == "block":
                yield StreamEvent(type=EventType.ERROR, content=f"Daily budget ${self._daily_limit} exceeded")
                return
            # warn: just log and continue
        async for event in next_handler(messages, ctx):
            yield event
```

**Step 3 — Verify Task 2.1-2.2:**

```bash
python -c "
from chainforge.enterprise.economics import CostTracker, BudgetGuard, CostReport
t = CostTracker(backend='memory')
r = t.report(period='today')
assert r.total == 0.0
assert r.to_json() == []
print('OK')
"
```

Commit: `feat: Phase 2 — Agent Economics Layer`

---

## Phase 3: Collective Agent Memory (Module 4)

### Task 3.1: Experience data model + CollectiveMemory core

**Files:**
- Create: `chainforge/enterprise/collective/__init__.py`
- Create: `chainforge/enterprise/collective/experience.py`
- Create: `chainforge/enterprise/collective/memory.py`
- Create: `chainforge/enterprise/collective/forgetting.py`

`experience.py` — `Experience` pydantic model with fields: id, task, task_type, tools_used, model_used, outcome, feedback, cost, tokens, duration_ms, timestamp, decay_factor.

`forgetting.py` — `ForgettingCurve.ebbinghaus(days_since: float) -> float` (Ebbinghaus decay: `1.0 / (1.0 + days_since * 0.1)`)

`memory.py`:
```python
class CollectiveMemory:
    """Shared experience pool for multiple agents."""
    def __init__(self, backend="sqlite", namespace="default", forgetting_curve="ebbinghaus"):
        self._experiences: list[Experience] = []
        self._namespace = namespace
        self._forgetting = forgetting_curve
    def add(self, exp: Experience): self._experiences.append(exp)
    def search(self, task_hint: str, limit=5, min_success_rate=0.0) -> list[Experience]:
        # Simple keyword match + decay factor. Real version uses embeddings.
        results = [e for e in self._experiences if any(w in e.task.lower() for w in task_hint.lower().split())]
        if min_success_rate > 0: results = [e for e in results if (1.0 if e.outcome=="success" else 0.0) >= min_success_rate]
        results.sort(key=lambda e: e.timestamp * e.decay_factor, reverse=True)
        return results[:limit]
    def export(self, format="json") -> list[dict]:
        return [e.model_dump() for e in self._experiences]
```

### Task 3.2: ExperienceRecorder middleware + ExperienceRetriever + ConflictResolver

**Files:**
- Create: `chainforge/enterprise/collective/recorder.py`
- Create: `chainforge/enterprise/collective/retriever.py`
- Create: `chainforge/enterprise/collective/resolver.py`

`recorder.py` — `ExperienceRecorder(memory: CollectiveMemory)` returns a middleware that auto-records Experience after each run.

`retriever.py` — `ExperienceRetriever(memory: CollectiveMemory).search(task, limit, min_success_rate) -> list[Experience]`

`resolver.py`:
```python
class ConflictResolver:
    """Find conflicting experiences and resolve them."""
    def __init__(self, memory: CollectiveMemory): ...
    def find_conflicts(self) -> list[ConflictResolution]:
        """Group experiences by task_type, find outcome contradictions."""
        ...
```

**Step 3 — Verify:**

```bash
python -c "
from chainforge.enterprise.collective import CollectiveMemory, Experience, ForgettingCurve
cm = CollectiveMemory(backend='memory')
cm.add(Experience(id='1', task='refund order', task_type='refund', tools_used=['refund_tool'],
       model_used='gpt-4o', outcome='success', cost=0.05, tokens=500, duration_ms=800, timestamp=1000))
results = cm.search('refund', limit=3)
assert len(results) == 1
assert cm.export()  # returns list[dict]
print('OK')
"
```

Commit: `feat: Phase 3 — Collective Agent Memory`

---

## Phase 4: Supply Chain Security (Module 3)

### Task 4.1: SupplyChainScanner + PermissionPolicy + SBOMExporter

**Files:**
- Create: `chainforge/enterprise/supply_chain/__init__.py`
- Create: `chainforge/enterprise/supply_chain/dependency.py`
- Create: `chainforge/enterprise/supply_chain/scanner.py`
- Create: `chainforge/enterprise/supply_chain/policy.py`
- Create: `chainforge/enterprise/supply_chain/sbom.py`
- Create: `chainforge/enterprise/supply_chain/mcp_verifier.py`

`dependency.py` — `DependencyAnalyzer.analyze(tool_or_callable) -> DepInfo(name, imports, cves)`. Uses `inspect.getmodule()` + `ast.parse()` to extract import statements.

`scanner.py`:
```python
class SupplyChainReport(BaseModel):
    tools: list[dict] = []
    skills: list[dict] = []
    mcp_servers: list[dict] = []
    total_risk_score: float = 0.0
    def to_json(self): return self.model_dump()

class SupplyChainScanner:
    def scan(self, agent) -> SupplyChainReport: ...
    def recommend_policy(self, agent) -> PermissionPolicy: ...
```

`policy.py` — `PermissionPolicy(allowed_tools, blocked_tools, mcp_constraints)`, `.to_yaml(path)`, `.as_middleware() -> Callable`.

`sbom.py` — `SBOMExporter.export(agent, format="spdx") -> SBOMDocument`, `.save(path)`.

`mcp_verifier.py` — `MCPVerifier.verify(url) -> MCPVerification {risk, data_exfiltration_risk, domains_contacted}`.

**Step 2 — Verify:**

```bash
python -c "
from chainforge.enterprise.supply_chain import SupplyChainScanner, PermissionPolicy, SBOMExporter
policy = PermissionPolicy(allowed_tools=['query_db'], blocked_tools=['delete_file'])
yaml_str = policy.to_yaml()
assert 'allowed_tools' in yaml_str or 'query_db' in yaml_str
print('OK')
"
```

Commit: `feat: Phase 4 — Agent Supply Chain Security`

---

## 最终验证

```bash
python -c "
from chainforge.enterprise.compliance import RiskClassifier, HITLPolicy, ComplianceAuditor
from chainforge.enterprise.economics import CostTracker, BudgetGuard
from chainforge.enterprise.collective import CollectiveMemory, Experience
from chainforge.enterprise.supply_chain import SupplyChainScanner, PermissionPolicy
print('All imports OK')
"
```

---

## 实施顺序

```
Phase 1 (Compliance) → Phase 2 (Economics) → Phase 3 (Collective) → Phase 4 (Supply Chain)
      4 files              3 files              6 files                   6 files
      ~300 lines           ~250 lines           ~350 lines                ~350 lines
```

总计: ~19 files, ~1,250 lines, 无 breaking changes.
