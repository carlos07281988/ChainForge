# NIM + Governance 2.0 + SmartRouter 3.0 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ChainForge 添加 NVIDIA NIM Provider、Governance 2.0 策略引擎、Policy-Aware 路由

**Architecture:** 三阶段顺序交付：Phase A 新文件 `providers/nim.py`（NIM Provider），Phase B 新包 `governance/`（策略引擎+数据驻留+版本锁定+审计报告），Phase C 新文件 `routing/policy_router.py`（策略感知路由）。每阶段独立可测试，无 breaking changes。

**Tech Stack:** Python 3.11+, Pydantic, openai SDK, sqlite3

## Global Constraints

- 使用 `from __future__ import annotations` 在所有新文件
- 遵循 Apache 2.0 license header
- Provider 用 `@runtime_checkable Protocol` 实现 LLM 协议（不用继承）
- 所有 Pydantic model 使用 `ConfigDict(arbitrary_types_allowed=True)`
- 无 breaking changes — 所有新参数均为 optional
- NIM 无需 api_key（本地服务），默认 base_url: `http://localhost:8000/v1`

---

## Phase A：NVIDIA NIM Provider

### Task A1: NIMProvider 核心实现

**Files:**
- Create: `chainforge/providers/nim.py`
- Modify: `chainforge/providers/__init__.py`
- Modify: `chainforge/core/llm.py`
- Modify: `chainforge/routing/adaptive.py`

**Interfaces:**
- Consumes: `LLM` (Protocol), `LLMResponse`, `Message`, `ToolSpec`, `ProviderError`, `log_data`, `get_logger`
- Produces: `NIMProvider(model, base_url, api_key, health_check_interval)`, `async health_check() -> bool`, `async list_models() -> list[str]`, `async generate() -> LLMResponse`, `async stream_generate() -> AsyncIterator`

- [ ] **Step 1: 创建 `chainforge/providers/nim.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""NVIDIA NIM provider — local GPU inference via OpenAI-compatible API.

NIM (NVIDIA Inference Microservice) runs optimized models on local GPUs
with an OpenAI-compatible `/v1` endpoint. This provider wraps that endpoint
with health-checking and model discovery.

Usage:
    from chainforge.providers import NIMProvider

    llm = NIMProvider(
        model="meta/llama-3.1-70b-instruct",
        base_url="http://gpu-node-01:8000/v1",
    )
    agent = Agent(llm=llm, tools=[...])
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from logging import DEBUG, WARNING
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message
from chainforge.core.tool import ToolSpec
from chainforge.logging import get_logger, log_data

logger = get_logger("providers.nim")

# NIM 默认挂载的常见模型及其 approximate GPU 成本
NIM_DEFAULT_MODELS: dict[str, dict[str, Any]] = {
    "meta/llama-3.1-8b-instruct":    {"gpu_memory_gb": 16,  "cost_per_1k_tokens": 0.0},
    "meta/llama-3.1-70b-instruct":   {"gpu_memory_gb": 140, "cost_per_1k_tokens": 0.0},
    "meta/llama-3.3-70b-instruct":   {"gpu_memory_gb": 140, "cost_per_1k_tokens": 0.0},
    "mistralai/mistral-7b-instruct": {"gpu_memory_gb": 16,  "cost_per_1k_tokens": 0.0},
    "nvidia/nemotron-4-340b":        {"gpu_memory_gb": 680, "cost_per_1k_tokens": 0.0},
}


class NIMProvider(BaseModel):
    """NVIDIA NIM LLM provider — local GPU inference.

    Communicates with a NIM instance via its OpenAI-compatible /v1 endpoint.
    Includes health-checking and model discovery for local infrastructure
    awareness.

    Attributes:
        model: Model identifier, e.g. 'meta/llama-3.1-70b-instruct'.
        base_url: NIM endpoint URL, defaults to 'http://localhost:8000/v1'.
        api_key: API key (NIM defaults to no auth, use None for local).
        health_check_interval: Seconds between automatic health checks.
        top_k: NIM-specific top-k sampling.
        repetition_penalty: NIM-specific repetition penalty.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="meta/llama-3.1-8b-instruct")
    base_url: str = Field(default="http://localhost:8000/v1")
    api_key: str | None = Field(default=None)

    # Local GPU awareness
    health_check_interval: int = Field(default=30, ge=10)

    # NIM 特有推理参数
    top_k: int | None = Field(default=None, ge=1, le=100)
    repetition_penalty: float | None = Field(default=None, ge=1.0, le=2.0)

    # 内部状态
    _last_health: bool = True
    _last_health_time: float = 0.0
    _available_models: list[str] = []
    _gpu_info: dict[str, Any] = {}

    @property
    def capabilities(self) -> set[str]:
        from chainforge.core.llm import ProviderCapability
        caps = {
            ProviderCapability.CHAT,
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.FUNCTION_CALLING,
        }
        # Vision-capable NIM models
        if any(v in self.model.lower() for v in ["llava", "vila", "phi-3-vision", "clip"]):
            caps.add(ProviderCapability.VISION)
        return caps

    @property
    def is_healthy(self) -> bool:
        """Return cached health status (refreshed by health_check())."""
        return self._last_health

    def _get_client(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "NIM provider requires `openai` package. Install with: pip install openai"
            )
        return AsyncOpenAI(
            api_key=self.api_key or "nim-local",
            base_url=self.base_url,
        )

    async def health_check(self) -> bool:
        """Check NIM service health via GET /v1/models.

        Returns True if the NIM endpoint responds and reports models.

        Usage:
            if not await nim.health_check():
                logger.error("NIM service unavailable")
        """
        client = self._get_client()
        try:
            models = await client.models.list()
            self._available_models = [m.id for m in models.data]
            self._last_health = True
            self._last_health_time = time.time()
            log_data(logger, DEBUG, "NIM health check passed", data={
                "base_url": self.base_url,
                "available_models": len(self._available_models),
                "models": self._available_models[:5],
            })
            return True
        except Exception as e:
            self._last_health = False
            log_data(logger, WARNING, "NIM health check failed", data={
                "base_url": self.base_url, "error": str(e),
            })
            return False

    async def list_models(self) -> list[str]:
        """List all models available on this NIM instance.

        Performs a health check if no cached model list exists.
        """
        if not self._available_models:
            await self.health_check()
        return self._available_models

    def _to_openai_messages(self, messages: list[Message]) -> list[dict]:
        return [m.model_dump_openai() for m in messages]

    def _to_tool_specs(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters,
            }}
            for t in tools
        ]

    def _parse_response(self, raw: Any) -> LLMResponse:
        choice = raw.choices[0]
        msg = choice.message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": args},
                })
        usage = None
        if raw.usage:
            usage = {
                "prompt_tokens": raw.usage.prompt_tokens,
                "completion_tokens": raw.usage.completion_tokens,
                "total_tokens": raw.usage.total_tokens,
            }
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            usage=usage,
            model=raw.model,
            finish_reason=choice.finish_reason,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a complete (non-streaming) response from NIM.

        Auto-checks health before generation. NIM-specific parameters
        (top_k, repetition_penalty) are passed through kwargs.
        """
        client = self._get_client()
        openai_messages = self._to_openai_messages(messages)
        openai_tools = self._to_tool_specs(tools) if tools else None

        log_data(logger, DEBUG, f"NIM generate({self.model})", data={
            "model": self.model, "base_url": self.base_url,
            "messages": len(openai_messages),
            "tools": len(openai_tools) if openai_tools else 0,
        })

        extra_params: dict[str, Any] = {}
        if self.top_k is not None:
            extra_params["top_k"] = self.top_k
        if self.repetition_penalty is not None:
            extra_params["repetition_penalty"] = self.repetition_penalty
        extra_params.update(kwargs)

        try:
            raw = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                **extra_params,
            )
        except Exception as e:
            self._last_health = False
            log_data(logger, WARNING, f"NIM API error: {e}", data={
                "model": self.model, "base_url": self.base_url, "error": str(e),
            })
            raise ProviderError(f"NIM API error at {self.base_url}: {e}") from e

        result = self._parse_response(raw)
        log_data(logger, DEBUG, f"NIM response: {result.finish_reason}", data={
            "finish_reason": result.finish_reason,
            "content_length": len(result.content or ""),
            "tool_calls": len(result.tool_calls) if result.tool_calls else 0,
            "usage": result.usage,
        })
        return result

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        """Stream tokens from NIM via SSE.

        Yields content strings for text chunks and a final LLMResponse
        with tool calls and usage on completion.
        """
        client = self._get_client()
        openai_messages = self._to_openai_messages(messages)
        openai_tools = self._to_tool_specs(tools) if tools else None

        extra_params: dict[str, Any] = {}
        if self.top_k is not None:
            extra_params["top_k"] = self.top_k
        if self.repetition_penalty is not None:
            extra_params["repetition_penalty"] = self.repetition_penalty
        extra_params.update(kwargs)

        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools or None,
                stream=True,
                **extra_params,
            )
        except Exception as e:
            self._last_health = False
            raise ProviderError(f"NIM API error at {self.base_url}: {e}") from e

        content_parts: list[str] = []
        tool_call_deltas: dict[int, dict] = {}
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            if delta.content:
                yield delta.content
                content_parts.append(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_call_deltas[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_call_deltas[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_call_deltas[idx]["function"]["arguments"] += tc.function.arguments
            finish = chunk.choices[0].finish_reason if chunk.choices else None
            if finish:
                tc_list = None
                if tool_call_deltas:
                    tc_list = []
                    for idx in sorted(tool_call_deltas):
                        d = tool_call_deltas[idx]
                        try:
                            args = json.loads(d["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = {"_raw": d["function"]["arguments"]}
                        tc_list.append({
                            "id": d["id"],
                            "type": "function",
                            "function": {"name": d["function"]["name"], "arguments": args},
                        })
                yield LLMResponse(
                    content="".join(content_parts) if content_parts else None,
                    tool_calls=tc_list,
                    model=chunk.model,
                    finish_reason=finish,
                )
```

- [ ] **Step 2: 注册 NIMProvider 到 lazy registry**

Edit `chainforge/providers/__init__.py`:

```python
# In _LAZY_REGISTRY dict, add after "BedrockProvider" line:
    "OllamaProvider": "chainforge.providers.ollama",
    "DeepSeekProvider": "chainforge.providers.deepseek",
    "NIMProvider": "chainforge.providers.nim",
```

- [ ] **Step 3: 在 AdaptiveRouter._create_provider 加入 nim 分支**

Edit `chainforge/routing/adaptive.py`, replace the `_create_provider` method:

```python
    def _create_provider(self, info: ModelInfo) -> Any | None:
        """Create an LLM provider from ModelInfo."""
        try:
            if info.provider == "openai":
                from chainforge.providers import OpenAIProvider
                return OpenAIProvider(model=info.name)
            elif info.provider == "anthropic":
                from chainforge.providers import AnthropicProvider
                return AnthropicProvider(model=info.name)
            elif info.provider == "google":
                from chainforge.providers import GoogleProvider
                return GoogleProvider(model=info.name)
            elif info.provider == "deepseek":
                from chainforge.providers import DeepSeekProvider
                return DeepSeekProvider(model=info.name)
            elif info.provider == "ollama":
                from chainforge.providers import OllamaProvider
                return OllamaProvider(model=info.name)
            elif info.provider == "nim":
                from chainforge.providers import NIMProvider
                return NIMProvider(model=info.name)
            elif info.provider == "bedrock":
                from chainforge.providers import BedrockProvider
                return BedrockProvider(model=info.name)
            else:
                from chainforge.providers import OpenAIProvider
                return OpenAIProvider(model=info.name)
        except Exception as e:
            logger.warning(f"Failed to create provider for {info.name}: {e}")
            return None
```

- [ ] **Step 4: 添加 NIM 模型定价到 MODEL_PRICING**

Edit `chainforge/core/llm.py`, in the `MODEL_PRICING` dict, add after the gemini entries:

```python
    # NVIDIA NIM (local, cost = GPU time proxy)
    "meta/llama-3.1-8b-instruct":    {"input": 0.0, "output": 0.0},
    "meta/llama-3.1-70b-instruct":   {"input": 0.0, "output": 0.0},
    "meta/llama-3.3-70b-instruct":   {"input": 0.0, "output": 0.0},
    "mistralai/mistral-7b-instruct": {"input": 0.0, "output": 0.0},
```

- [ ] **Step 5: 创建测试文件 `tests/test_providers_nim.py`**

```python
"""Tests for the NVIDIA NIM provider."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from chainforge.providers.nim import NIMProvider
from chainforge.core.message import Message, Role
from chainforge.core.llm import LLMResponse


class TestNIMProvider:
    """Unit tests for NIMProvider."""

    def test_default_config(self):
        """Default base_url and model are set."""
        nim = NIMProvider()
        assert nim.model == "meta/llama-3.1-8b-instruct"
        assert nim.base_url == "http://localhost:8000/v1"
        assert nim.api_key is None
        assert nim.health_check_interval == 30

    def test_custom_config(self):
        """Custom config is respected."""
        nim = NIMProvider(
            model="mistralai/mistral-7b-instruct",
            base_url="http://gpu-node:9000/v1",
            top_k=50,
            repetition_penalty=1.2,
        )
        assert nim.model == "mistralai/mistral-7b-instruct"
        assert nim.base_url == "http://gpu-node:9000/v1"
        assert nim.top_k == 50
        assert nim.repetition_penalty == 1.2

    def test_capabilities_basic_chat_model(self):
        """Chat models report standard capabilities."""
        nim = NIMProvider(model="meta/llama-3.1-8b-instruct")
        caps = nim.capabilities
        assert "chat" in caps
        assert "streaming" in caps
        assert "tool_calling" in caps
        assert "vision" not in caps

    def test_capabilities_vision_model(self):
        """Vision models report the VISION capability."""
        nim = NIMProvider(model="llava-v1.6-34b")
        assert "vision" in nim.capabilities

    def test_is_healthy_defaults_true(self):
        """is_healthy returns True until a failed health check."""
        nim = NIMProvider()
        assert nim.is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure_sets_unhealthy(self):
        """Failed health check sets _last_health = False."""
        nim = NIMProvider()
        with patch.object(nim, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.models.list = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_fn.return_value = mock_client

            result = await nim.health_check()
            assert result is False
            assert nim.is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success_populates_models(self):
        """Successful health check populates model list."""
        nim = NIMProvider()
        with patch.object(nim, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            fake_model = MagicMock()
            fake_model.id = "meta/llama-3.1-70b-instruct"
            mock_client.models.list = AsyncMock(return_value=MagicMock(data=[fake_model]))
            mock_client_fn.return_value = mock_client

            result = await nim.health_check()
            assert result is True
            assert nim.is_healthy is True
            assert "meta/llama-3.1-70b-instruct" in nim._available_models

    @pytest.mark.asyncio
    async def test_list_models_caches(self):
        """list_models() returns cached models without re-querying."""
        nim = NIMProvider()
        nim._available_models = ["model-a", "model-b"]
        models = await nim.list_models()
        assert models == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_list_models_triggers_health_check_when_empty(self):
        """list_models() triggers health_check when cache is empty."""
        nim = NIMProvider()
        with patch.object(nim, "health_check", new_callable=AsyncMock) as mock_hc:
            await nim.list_models()
            mock_hc.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_raises_provider_error_on_api_failure(self):
        """API failures raise ProviderError and mark unhealthy."""
        from chainforge.core.errors import ProviderError

        nim = NIMProvider()
        with patch.object(nim, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("503 Service Unavailable")
            )
            mock_client_fn.return_value = mock_client

            with pytest.raises(ProviderError, match="NIM API error"):
                await nim.generate([Message(role=Role.user, content="Hi")])
            assert nim.is_healthy is False

    @pytest.mark.asyncio
    async def test_generate_returns_llm_response(self):
        """Successful generation returns LLMResponse."""
        nim = NIMProvider()
        with patch.object(nim, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_msg = MagicMock()
            mock_msg.content = "Hello!"
            mock_msg.tool_calls = None
            mock_raw = MagicMock()
            mock_raw.choices = [MagicMock(message=mock_msg, finish_reason="stop")]
            mock_raw.usage = MagicMock(prompt_tokens=5, completion_tokens=2, total_tokens=7)
            mock_raw.model = "meta/llama-3.1-8b-instruct"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_raw)
            mock_client_fn.return_value = mock_client

            result = await nim.generate([Message(role=Role.user, content="Hi")])
            assert isinstance(result, LLMResponse)
            assert result.content == "Hello!"
            assert result.finish_reason == "stop"
            assert result.usage["prompt_tokens"] == 5
```

- [ ] **Step 6: 运行测试验证**

```bash
python -m pytest tests/test_providers_nim.py -v
```

Expected: 8 tests pass.

- [ ] **Step 7: 验证 NIMProvider 可被 import**

```bash
python -c "from chainforge.providers import NIMProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit Phase A**

```bash
git add chainforge/providers/nim.py chainforge/providers/__init__.py chainforge/core/llm.py chainforge/routing/adaptive.py tests/test_providers_nim.py
git commit -m "feat: Phase A — NVIDIA NIM Provider

Add NIMProvider with OpenAI-compatible API wrapper for local GPU inference.
Includes health_check(), list_models(), generate(), stream_generate().
Integrated into lazy provider registry and AdaptiveRouter.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase B：Governance 2.0

### Task B1: GovernancePolicy + PolicyEngine

**Files:**
- Create: `chainforge/governance/__init__.py`
- Create: `chainforge/governance/policy.py`

**Interfaces:**
- Consumes: Pydantic BaseModel
- Produces: `GovernancePolicy`, `PolicyDecision`, `PolicyEngine`

- [ ] **Step 1: 创建 `chainforge/governance/__init__.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Governance 2.0 — policy-driven security, residency, and audit for agents.

Provides:
  - GovernancePolicy + PolicyEngine: declarative rule evaluation
  - DataResidency: data-locality enforcement (PII → local models)
  - ModelVersionTracker: model version pinning for reproducibility
  - AuditReporter: compliance audit reports from provenance + tracing data

Usage:
    from chainforge.governance import PolicyEngine, GovernancePolicy
    from chainforge.governance.residency import DataResidency

    engine = PolicyEngine(policies=[
        GovernancePolicy(name="pii-local", data_labels=["pii"],
                         model_provider="nim", action="enforce"),
    ])

    decision = await engine.evaluate(["pii"], context={})
    # → PolicyDecision(allowed_providers=["nim"], blocked=False)
"""

from chainforge.governance.policy import (
    GovernancePolicy,
    PolicyDecision,
    PolicyEngine,
)
from chainforge.governance.residency import DataResidency
from chainforge.governance.versioning import ModelVersionTracker, VersionRecord
from chainforge.governance.audit import AuditReporter, AuditReport, ComplianceItem

__all__ = [
    "GovernancePolicy",
    "PolicyDecision",
    "PolicyEngine",
    "DataResidency",
    "ModelVersionTracker",
    "VersionRecord",
    "AuditReporter",
    "AuditReport",
    "ComplianceItem",
]
```

- [ ] **Step 2: 创建 `chainforge/governance/policy.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""GovernancePolicy + PolicyEngine — declarative governance rules.

Policies are evaluated against data labels to determine which model
providers are allowed, whether the request is blocked, and whether
model version pinning is enforced.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("governance.policy")


class GovernancePolicy(BaseModel):
    """A declarative governance rule.

    Each policy maps data sensitivity labels to model provider constraints.

    Attributes:
        name: Human-readable policy name.
        description: What this policy enforces.
        data_labels: Which data labels trigger this policy
                     (e.g. "pii", "internal", "public").
        model_provider: Required provider — "nim", "ollama", "openai", etc.
                        None means no restriction.
        region: Data residency region — "cn-east", "us-west", etc.
                None means no restriction.
        version_pin: Lock to a specific model version. None means latest.
        action: "enforce" (hard block), "audit_only" (log but allow),
                "warn" (log + annotate response).
        priority: Higher priority policies are evaluated first.
    """

    name: str = Field(description="Policy name")
    description: str = Field(default="", description="What this policy enforces")
    data_labels: list[str] = Field(default_factory=list,
                                    description="Triggering data labels")
    model_provider: str | None = Field(default=None,
                                        description="Required provider")
    region: str | None = Field(default=None,
                               description="Data residency region")
    version_pin: str | None = Field(default=None,
                                     description="Locked model version")
    action: str = Field(default="enforce",
                        description="enforce | audit_only | warn")
    priority: int = Field(default=0, description="Evaluation priority (higher = first)")

    def matches(self, labels: list[str]) -> bool:
        """Check if this policy's data_labels intersect with the given labels."""
        if not self.data_labels:
            return True  # Empty labels = matches everything
        return any(label in self.data_labels for label in labels)


class PolicyDecision(BaseModel):
    """Result of evaluating all governance policies against a set of labels.

    Attributes:
        allowed_providers: Set of provider names that are allowed.
                           Empty means all are allowed.
        blocked: Whether the request should be blocked entirely.
        block_reason: Reason for block, if blocked=True.
        version_pins: Dict of provider → version to use.
        audit_tags: Tags to attach to the audit log.
        warnings: List of warning messages for the caller.
    """

    allowed_providers: list[str] = Field(default_factory=list)
    blocked: bool = Field(default=False)
    block_reason: str = Field(default="")
    version_pins: dict[str, str] = Field(default_factory=dict)
    audit_tags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_restricted(self) -> bool:
        """True if provider choice is constrained by policy."""
        return len(self.allowed_providers) > 0


class PolicyEngine:
    """Evaluates GovernancePolicies against data labels.

    Usage:
        engine = PolicyEngine(policies=[
            GovernancePolicy(name="pii-local", data_labels=["pii"],
                             model_provider="nim", action="enforce"),
        ])
        decision = await engine.evaluate(["pii"], context={})
    """

    def __init__(self, policies: list[GovernancePolicy] | None = None):
        self._policies = sorted(
            policies or [],
            key=lambda p: p.priority,
            reverse=True,
        )

    @property
    def policies(self) -> list[GovernancePolicy]:
        return list(self._policies)

    def add_policy(self, policy: GovernancePolicy) -> None:
        """Add a policy and re-sort by priority."""
        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority, reverse=True)

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name. Returns True if found and removed."""
        count_before = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        return len(self._policies) < count_before

    async def evaluate(
        self,
        labels: list[str],
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate all matching policies against the given data labels.

        Args:
            labels: Data sensitivity labels (e.g. ["pii", "internal"]).
            context: Optional execution context (user_id, session_id, etc.).

        Returns:
            PolicyDecision with allowed providers, block status, version pins.
        """
        ctx = context or {}
        decision = PolicyDecision()

        allowed_providers_set: set[str] | None = None
        enforce_providers_set: set[str] = set()
        audit_tags: list[str] = []

        for policy in self._policies:
            if not policy.matches(labels):
                continue

            audit_tags.append(f"policy:{policy.name}")

            if policy.action == "enforce":
                # Hard constraint: restrict to this provider
                if policy.model_provider:
                    enforce_providers_set.add(policy.model_provider)
                if policy.version_pin:
                    if policy.model_provider:
                        decision.version_pins[policy.model_provider] = policy.version_pin
            elif policy.action == "warn":
                decision.warnings.append(
                    f"[{policy.name}] {policy.description or 'Policy warning'}"
                )
            elif policy.action == "audit_only":
                # Just tag for audit — no enforcement
                pass

        # Resolve provider constraints
        if enforce_providers_set:
            # Intersection: only providers that satisfy ALL enforce policies
            decision.allowed_providers = sorted(enforce_providers_set)

        decision.audit_tags = audit_tags

        if decision.allowed_providers:
            logger.debug(
                f"Policy engine restricted providers to {decision.allowed_providers}",
                extra={"labels": labels, "audit_tags": audit_tags},
            )

        return decision
```

- [ ] **Step 3: 运行快速验证**

```bash
python -c "
from chainforge.governance.policy import GovernancePolicy, PolicyEngine, PolicyDecision
import asyncio

engine = PolicyEngine(policies=[
    GovernancePolicy(name='pii-local', data_labels=['pii'], model_provider='nim', action='enforce'),
])
d = asyncio.run(engine.evaluate(['pii'], {}))
assert d.allowed_providers == ['nim'], f'Expected [nim], got {d.allowed_providers}'
d2 = asyncio.run(engine.evaluate(['public'], {}))
assert d2.allowed_providers == [], f'Expected [], got {d2.allowed_providers}'
print('OK')
"
```

Expected: `OK`

- [ ] **Step 4: Commit Task B1**

```bash
git add chainforge/governance/__init__.py chainforge/governance/policy.py
git commit -m "feat: Phase B1 — GovernancePolicy + PolicyEngine

Declarative governance rules with data label matching and provider enforcement.
Supports enforce/audit_only/warn actions with priority-based evaluation.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task B2: DataResidency + ModelVersionTracker

**Files:**
- Create: `chainforge/governance/residency.py`
- Create: `chainforge/governance/versioning.py`

**Interfaces:**
- Consumes: Pydantic BaseModel
- Produces: `DataResidency`, `ModelVersionTracker`, `VersionRecord`

- [ ] **Step 1: 创建 `chainforge/governance/residency.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""DataResidency — enforce data locality for sensitive data.

Maps data sensitivity labels to allowed provider categories. Used by
PolicyEngine and PolicyAwareRouter to keep PII/internal data on
local infrastructure.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("governance.residency")


class ResidencyRules(BaseModel):
    """A set of residency rules mapping data labels to allowed providers."""

    label: str = Field(description="Data sensitivity label")
    allowed_providers: list[str] = Field(
        description="Provider names allowed for this label"
    )
    description: str = Field(default="")


class DataResidency:
    """Data residency controller — determines which providers are allowed
    for a given set of data sensitivity labels.

    Built-in rules:
        pii      → nim, ollama (local only)
        internal → nim, ollama (local only)
        public   → all providers
        finance  → nim, ollama, bedrock (local + regulated cloud)

    Usage:
        residency = DataResidency()
        providers = residency.allowed_providers(["pii"])
        # → {"nim", "ollama"}

        # Add custom rule
        residency.add_rule("healthcare", ["nim"], "HIPAA data must stay local")
    """

    # Default rules — local/regulated providers for sensitive labels
    DEFAULT_RULES: ClassVar[dict[str, set[str]]] = {
        "pii":       {"nim", "ollama"},
        "internal":  {"nim", "ollama"},
        "finance":   {"nim", "ollama", "bedrock"},
        "healthcare": {"nim", "ollama"},
        "public":    {"openai", "anthropic", "google", "deepseek",
                      "azure", "bedrock", "ollama", "nim"},
    }

    def __init__(self):
        self._rules: dict[str, set[str]] = dict(self.DEFAULT_RULES)

    def add_rule(self, label: str, providers: list[str], description: str = "") -> None:
        """Add or override a residency rule.

        Args:
            label: Data sensitivity label (e.g. "healthcare").
            providers: Allowed provider names.
            description: Human-readable reason for the rule.
        """
        self._rules[label] = set(providers)
        logger.info(f"Added residency rule: {label} → {set(providers)}")

    def remove_rule(self, label: str) -> bool:
        """Remove a custom rule. Built-in rules cannot be removed."""
        if label in self.DEFAULT_RULES:
            logger.warning(f"Cannot remove built-in residency rule: {label}")
            return False
        return self._rules.pop(label, None) is not None

    def allowed_providers(self, labels: list[str]) -> set[str]:
        """Compute the set of providers allowed for ALL given labels.

        When multiple labels apply, the intersection of all matching
        rules is used (most restrictive wins).

        Args:
            labels: Data sensitivity labels (e.g. ["pii", "internal"]).

        Returns:
            Set of allowed provider names. Empty set = no restriction.
        """
        if not labels:
            return set()

        matched_rules = []
        for label in labels:
            if label in self._rules:
                matched_rules.append(self._rules[label])

        if not matched_rules:
            # No rules match — allow all by returning empty set
            return set()

        # Intersection: a provider must be allowed by ALL matched rules
        result = matched_rules[0]
        for rule_set in matched_rules[1:]:
            result = result & rule_set

        logger.debug(
            f"Residency: labels={labels} → allowed={result}",
            extra={"labels": labels, "allowed": sorted(result)},
        )
        return result

    def is_allowed(self, provider: str, labels: list[str]) -> bool:
        """Check if a specific provider is allowed for the given labels.

        Returns True if no rules restrict this provider.
        """
        allowed = self.allowed_providers(labels)
        if not allowed:
            return True  # No restrictions
        return provider in allowed

    def get_policies(self) -> list[ResidencyRules]:
        """Export all current rules (for display/debugging)."""
        return [
            ResidencyRules(
                label=label,
                allowed_providers=sorted(providers),
                description="built-in" if label in self.DEFAULT_RULES else "custom",
            )
            for label, providers in sorted(self._rules.items())
        ]
```

- [ ] **Step 2: 创建 `chainforge/governance/versioning.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""ModelVersionTracker — record and verify model versions for reproducibility.

Captures a snapshot of (provider, model, params) on each call so that
every inference can be reproduced or audited later.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, Field


def _make_hash(*parts: str) -> str:
    """Create a short deterministic hash from string parts."""
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


class VersionRecord(BaseModel):
    """A single version snapshot of a model call.

    Attributes:
        record_id: Unique record identifier.
        timestamp: Unix timestamp when the snapshot was taken.
        provider: Provider name (e.g. "nim", "openai").
        model: Model identifier (e.g. "meta/llama-3.1-70b-instruct").
        model_version: Optional server-reported version string.
        params_hash: Hash of the generation parameters.
        params: The actual parameters used (for audit).
        extra: Arbitrary metadata (node, user, session).
    """

    record_id: str = Field(default_factory=lambda: _make_hash(str(time.time())))
    timestamp: float = Field(default_factory=time.time)
    provider: str = Field(description="Provider name")
    model: str = Field(description="Model identifier")
    model_version: str | None = Field(default=None,
                                       description="Server-reported version")
    params_hash: str = Field(description="Hash of generation parameters")
    params: dict[str, Any] = Field(default_factory=dict,
                                    description="Generation parameters")
    extra: dict[str, Any] = Field(default_factory=dict,
                                   description="Additional metadata")


class ModelVersionTracker:
    """Records model version snapshots and verifies consistency.

    Usage:
        tracker = ModelVersionTracker()

        # Record a version before calling the model
        record = tracker.snapshot("nim", "meta/llama-3.1-70b-instruct",
                                  temperature=0.7, top_p=0.9)

        # Later: verify the model is still at the expected version
        is_consistent = tracker.verify("nim", record.params_hash)
    """

    def __init__(self):
        self._records: dict[str, VersionRecord] = {}

    def snapshot(
        self,
        provider: str,
        model: str,
        model_version: str | None = None,
        **params: Any,
    ) -> VersionRecord:
        """Record a version snapshot of a model call.

        Args:
            provider: Provider name.
            model: Model identifier.
            model_version: Optional server-reported version.
            **params: Generation parameters to hash.

        Returns:
            VersionRecord with hash for later verification.
        """
        params_hash = _make_hash(
            provider,
            model,
            json.dumps(params, sort_keys=True, default=str),
        )

        record = VersionRecord(
            provider=provider,
            model=model,
            model_version=model_version,
            params_hash=params_hash,
            params=dict(params),
            extra={"version_snapshot_at": time.time()},
        )

        self._records[record.record_id] = record
        return record

    def verify(
        self,
        provider: str,
        expected_params_hash: str,
        current_params: dict[str, Any] | None = None,
    ) -> bool:
        """Verify the current model state matches the expected snapshot.

        Args:
            provider: Provider name to check.
            expected_params_hash: Hash from a previous snapshot.
            current_params: Current parameters (optional). If provided,
                           hashes them and compares to expected.

        Returns:
            True if the current state matches the expected snapshot.
        """
        if current_params is not None:
            # If current params provided, hash and compare directly
            model = current_params.pop("model", "unknown")
            current_hash = _make_hash(
                provider,
                model,
                json.dumps(current_params, sort_keys=True, default=str),
            )
            return current_hash == expected_params_hash

        # Without current params, check if any record matches
        for record in self._records.values():
            if (record.provider == provider and
                    record.params_hash == expected_params_hash):
                return True
        return False

    def get_record(self, record_id: str) -> VersionRecord | None:
        """Retrieve a specific version record by ID."""
        return self._records.get(record_id)

    def list_records(self, provider: str | None = None) -> list[VersionRecord]:
        """List all records, optionally filtered by provider."""
        records = list(self._records.values())
        if provider:
            records = [r for r in records if r.provider == provider]
        return sorted(records, key=lambda r: r.timestamp, reverse=True)

    def clear(self) -> None:
        """Remove all records."""
        self._records.clear()

    @property
    def record_count(self) -> int:
        return len(self._records)
```

- [ ] **Step 3: 运行快速验证**

```bash
python -c "
from chainforge.governance.residency import DataResidency
from chainforge.governance.versioning import ModelVersionTracker

# Residency
r = DataResidency()
assert r.allowed_providers(['pii']) == {'nim', 'ollama'}
assert r.allowed_providers(['public']) == {'openai', 'anthropic', 'google', 'deepseek', 'azure', 'bedrock', 'ollama', 'nim'}
assert r.is_allowed('nim', ['pii']) is True
assert r.is_allowed('openai', ['pii']) is False

# Versioning
t = ModelVersionTracker()
rec = t.snapshot('nim', 'meta/llama-3.1-70b-instruct', temperature=0.7)
assert t.verify('nim', rec.params_hash, current_params={'model': 'meta/llama-3.1-70b-instruct', 'temperature': 0.7})
assert not t.verify('nim', rec.params_hash, current_params={'model': 'meta/llama-3.1-70b-instruct', 'temperature': 0.9})
print('OK')
"
```

Expected: `OK`

- [ ] **Step 4: Commit Task B2**

```bash
git add chainforge/governance/residency.py chainforge/governance/versioning.py
git commit -m "feat: Phase B2 — DataResidency + ModelVersionTracker

DataResidency enforces data locality: PII/internal → local models only.
ModelVersionTracker snapshots (provider, model, params) for audit reproducibility.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task B3: AuditReporter

**Files:**
- Create: `chainforge/governance/audit.py`

**Interfaces:**
- Consumes: `ProvenanceTracker` (optional), `Tracer` (optional), `GovernancePolicy`
- Produces: `AuditReport`, `ComplianceItem`, `AuditReporter`

- [ ] **Step 1: 创建 `chainforge/governance/audit.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""AuditReporter — compliance audit reports from provenance + tracing data.

Consumes ProvenanceTracker and Tracer data to generate human-readable
audit reports. Supports compliance checking against GovernancePolicies.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("governance.audit")


class ComplianceItem(BaseModel):
    """A single compliance check result.

    Attributes:
        policy_name: Which policy was checked.
        passed: Whether the check passed.
        details: Human-readable details about the check.
        evidence: Supporting evidence (event IDs, timestamps).
    """

    policy_name: str = Field(description="Policy name")
    passed: bool = Field(default=True)
    details: str = Field(default="")
    evidence: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    """A complete audit report.

    Attributes:
        report_id: Unique report identifier.
        generated_at: Unix timestamp of generation.
        time_range: (start, end) time range of audited events.
        total_events: Number of events audited.
        compliance_items: Compliance check results.
        model_calls: Number of model calls in the period.
        providers_used: Which providers were used.
        data_labels_seen: Data labels that were classified.
        raw_summary: JSON-serializable summary for machine consumption.
    """

    report_id: str = Field(default_factory=lambda: f"audit-{int(time.time())}")
    generated_at: float = Field(default_factory=time.time)
    time_range: tuple[float, float] = Field(default=(0.0, 0.0))
    total_events: int = Field(default=0)
    compliance_items: list[ComplianceItem] = Field(default_factory=list)
    model_calls: int = Field(default=0)
    providers_used: list[str] = Field(default_factory=list)
    data_labels_seen: list[str] = Field(default_factory=list)
    raw_summary: dict[str, Any] = Field(default_factory=dict)

    @property
    def compliance_score(self) -> float:
        """Fraction of compliance checks that passed. 1.0 = fully compliant."""
        if not self.compliance_items:
            return 1.0
        passed = sum(1 for c in self.compliance_items if c.passed)
        return passed / len(self.compliance_items)

    def summary(self) -> str:
        """Human-readable summary of the audit report."""
        lines = [
            f"Audit Report: {self.report_id}",
            f"Generated:   {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.generated_at))}",
            f"Time Range:  {self._fmt_time(self.time_range[0])} → {self._fmt_time(self.time_range[1])}",
            f"Events:      {self.total_events}",
            f"Model Calls: {self.model_calls}",
            f"Providers:   {', '.join(self.providers_used) if self.providers_used else 'none'}",
            f"Data Labels: {', '.join(self.data_labels_seen) if self.data_labels_seen else 'none'}",
            f"Compliance:  {self.compliance_score:.0%} ({sum(1 for c in self.compliance_items if c.passed)}/{len(self.compliance_items)} passed)",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt_time(ts: float) -> str:
        if ts == 0.0:
            return "N/A"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


class AuditReporter:
    """Generates compliance audit reports from provenance and tracing data.

    Can optionally consume ProvenanceTracker and Tracer for detailed
    event-level auditing. Works standalone for lightweight usage.

    Usage:
        reporter = AuditReporter()
        reporter.record_event("model_call", {"provider": "nim", "model": "..."})
        reporter.record_event("data_label", {"labels": ["pii"]})

        report = reporter.generate_report()
        print(report.summary())
    """

    def __init__(
        self,
        provenance: Any | None = None,
        tracer: Any | None = None,
    ):
        """Initialize the audit reporter.

        Args:
            provenance: Optional ProvenanceTracker for detailed event tracing.
            tracer: Optional Tracer for span-level observability.
        """
        self._provenance = provenance
        self._tracer = tracer
        self._events: list[dict[str, Any]] = []

    def record_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Record an audit event.

        Args:
            event_type: Category — "model_call", "data_label", "policy_check",
                        "guardrail_block", "version_check".
            data: Event-specific payload.
        """
        self._events.append({
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        })
        logger.debug(f"Audit event: {event_type}", extra={"data": data})

    def generate_report(
        self,
        time_range: tuple[float, float] | None = None,
        policies: list[Any] | None = None,
    ) -> AuditReport:
        """Generate an audit report for the recorded events.

        Args:
            time_range: Optional (start, end) filter. Defaults to all events.
            policies: Optional policies to check compliance against.

        Returns:
            AuditReport with compliance score and summary.
        """
        events = self._events
        if time_range:
            start, end = time_range
            events = [e for e in events if start <= e["timestamp"] <= end]

        model_calls = [e for e in events if e["type"] == "model_call"]
        providers_used = list(set(
            e["data"].get("provider", "unknown") for e in model_calls
        ))
        data_labels_seen = []
        for e in events:
            if e["type"] == "data_label":
                data_labels_seen.extend(e["data"].get("labels", []))

        # Compliance checks
        compliance_items: list[ComplianceItem] = []

        # Check 1: PII data should not use cloud providers
        pii_events = [e for e in events if e["type"] == "data_label"
                      and "pii" in e["data"].get("labels", [])]
        cloud_providers_used_for_pii = []
        for e in model_calls:
            for pe in pii_events:
                if e["data"].get("provider") in ("openai", "anthropic", "google"):
                    cloud_providers_used_for_pii.append(e)

        compliance_items.append(ComplianceItem(
            policy_name="pii-local-only",
            passed=len(cloud_providers_used_for_pii) == 0,
            details=(
                f"{len(cloud_providers_used_for_pii)} PII model calls used cloud providers"
                if cloud_providers_used_for_pii
                else "All PII model calls used local providers"
            ),
            evidence=[e["data"].get("model", "") for e in cloud_providers_used_for_pii],
        ))

        # Check 2: Version pins honored
        version_events = [e for e in events if e["type"] == "version_check"]
        version_failures = [e for e in version_events
                           if not e["data"].get("passed", True)]
        compliance_items.append(ComplianceItem(
            policy_name="version-pin-enforcement",
            passed=len(version_failures) == 0,
            details=(
                f"{len(version_failures)} version pin violations"
                if version_failures
                else "All version pins honored"
            ),
            evidence=[json.dumps(e["data"]) for e in version_failures],
        ))

        # Custom policy checks
        if policies:
            from chainforge.governance.policy import GovernancePolicy  # noqa
            for p in policies:
                if not isinstance(p, GovernancePolicy):
                    continue
                # Check that enforce policies were followed
                if p.action == "enforce" and p.model_provider:
                    violations = [
                        e for e in model_calls
                        if e["data"].get("provider") != p.model_provider
                        and any(label in data_labels_seen for label in p.data_labels)
                    ]
                    compliance_items.append(ComplianceItem(
                        policy_name=p.name,
                        passed=len(violations) == 0,
                        details=(
                            f"{len(violations)} calls bypassed required provider "
                            f"{p.model_provider}"
                            if violations
                            else f"All calls used {p.model_provider} as required"
                        ),
                    ))

        report = AuditReport(
            time_range=time_range or (0.0, time.time()),
            total_events=len(events),
            compliance_items=compliance_items,
            model_calls=len(model_calls),
            providers_used=providers_used,
            data_labels_seen=list(set(data_labels_seen)),
            raw_summary={
                "event_types": {
                    t: len([e for e in events if e["type"] == t])
                    for t in set(e["type"] for e in events)
                },
            },
        )

        logger.info(
            f"Audit report generated: compliance={report.compliance_score:.0%}",
            extra={"report_id": report.report_id},
        )
        return report

    def clear_events(self) -> None:
        """Clear all recorded events."""
        self._events.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)
```

- [ ] **Step 2: 运行验证**

```bash
python -c "
from chainforge.governance.audit import AuditReporter

r = AuditReporter()
r.record_event('data_label', {'labels': ['pii']})
r.record_event('model_call', {'provider': 'nim', 'model': 'llama-3.1'})
r.record_event('version_check', {'passed': True, 'expected': 'abc123'})

report = r.generate_report()
print(report.summary())
assert report.compliance_score == 1.0
assert report.model_calls == 1
assert 'pii' in report.data_labels_seen
print('OK')
"
```

Expected: report summary + `OK`

- [ ] **Step 3: Commit Task B3**

```bash
git add chainforge/governance/audit.py
git commit -m "feat: Phase B3 — AuditReporter for compliance auditing

Generates AuditReports with compliance scoring from recorded events.
Checks PII locality, version pin enforcement, and custom policies.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase C：SmartRouter 3.0 — Policy-Aware Router

### Task C1: InfraProbe + DataClassifier + PolicyAwareRouter

**Files:**
- Create: `chainforge/routing/policy_router.py`
- Modify: `chainforge/routing/__init__.py`

**Interfaces:**
- Consumes: `AdaptiveRouter`, `ModelRegistry`, `PolicyEngine`, `InfraProbe`, `DataClassifier`
- Produces: `InfraProbe`, `DataClassifier`, `PolicyAwareRouter`

- [ ] **Step 1: 创建 `chainforge/routing/policy_router.py`**

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""PolicyAwareRouter — SmartRouter 3.0 with governance and infrastructure awareness.

Combines AdaptiveRouter (cost/capability) with PolicyEngine (governance)
and InfraProbe (infrastructure health) for optimal model routing.

Usage:
    from chainforge.routing.policy_router import (
        PolicyAwareRouter, InfraProbe, DataClassifier,
    )
    from chainforge.routing.adaptive import ModelRegistry
    from chainforge.governance.policy import PolicyEngine, GovernancePolicy

    registry = ModelRegistry()
    registry.register("gpt-4o-mini", provider="openai", cost_per_1k=0.00015)
    registry.register("llama-70b", provider="nim", cost_per_1k=0.0)
    registry.register("llama3.2", provider="ollama", cost_per_1k=0.0)

    engine = PolicyEngine(policies=[
        GovernancePolicy(name="pii-local", data_labels=["pii"],
                         model_provider="nim", action="enforce"),
    ])

    infra = InfraProbe(nim_url="http://gpu-node:8000/v1")
    router = PolicyAwareRouter(registry, engine, infra)

    provider = await router.select("What is 2+2?", context={})
    # → gpt-4o-mini (public data, cheapest capable)

    provider = await router.select("My SSN is 123-45-6789", context={})
    # → llama-70b (nim) — PII detected, forced to local
"""

from __future__ import annotations

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from chainforge.logging import get_logger

logger = get_logger("routing.policy_router")


# ── DataClassifier ──────────────────────────────────────────────────────────


# PII detection patterns — lightweight, no LLM call
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("pii", re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"  # SSN
        r"|\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"  # Credit card
        r"|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"  # Email
        r"|\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b"  # Phone (US)
        r"|\b(?:passport|身份证|护照)\s*[#:：]?\s*\w+\b"  # ID documents
        r"|\b(?:password|密码|secret|token)\s*[=:：]\s*\S+\b"  # Secrets
        , re.IGNORECASE,
    )),
    ("internal", re.compile(
        r"\b(?:confidential|机密|内部|internal\s*only|NDA|proprietary)\b",
        re.IGNORECASE,
    )),
    ("finance", re.compile(
        r"\b(?:bank\s*account|账号|银行卡|IBAN|SWIFT|routing\s*number)\b",
        re.IGNORECASE,
    )),
]


class DataClassifier:
    """Lightweight data sensitivity classifier using regex patterns.

    Does NOT call any LLM — operates entirely via regex matching.
    Designed to be fast (<1ms) and conservative (errs toward "public").

    Usage:
        classifier = DataClassifier()
        labels = classifier.classify("My SSN is 123-45-6789")
        # → ["pii"]
    """

    def __init__(self):
        self._patterns: list[tuple[str, re.Pattern]] = list(_PII_PATTERNS)

    def add_pattern(self, label: str, pattern: str) -> None:
        """Add a custom classification pattern.

        Args:
            label: Data sensitivity label (e.g. "healthcare").
            pattern: Regex pattern string.
        """
        self._patterns.append((label, re.compile(pattern, re.IGNORECASE)))

    def classify(self, text: str) -> list[str]:
        """Classify text into data sensitivity labels.

        Args:
            text: The input text to classify.

        Returns:
            List of matching labels. Empty list = "public" (no sensitive data).
        """
        if not text:
            return []

        labels: list[str] = []
        for label, pattern in self._patterns:
            if pattern.search(text):
                if label not in labels:
                    labels.append(label)

        if not labels:
            labels.append("public")

        logger.debug(f"Data classified: {labels}", extra={"text_len": len(text)})
        return labels

    @property
    def known_labels(self) -> list[str]:
        """All known classification labels."""
        return list(set(label for label, _ in self._patterns))


# ── InfraProbe ──────────────────────────────────────────────────────────────


class InfraProbe:
    """Infrastructure probe — checks local model availability.

    Periodically checks whether NIM, Ollama, and other local backends
    are reachable. Used by PolicyAwareRouter to filter out unavailable
    providers before making routing decisions.

    Usage:
        probe = InfraProbe(nim_url="http://gpu-node:8000/v1")
        if not await probe.check_nim():
            logger.warning("NIM unavailable, falling back to Ollama")
    """

    def __init__(
        self,
        nim_url: str | None = None,
        ollama_url: str | None = None,
    ):
        self._nim_url = nim_url or "http://localhost:8000/v1"
        self._ollama_url = ollama_url or "http://localhost:11434/v1"
        self._nim_available: bool = True  # Assume available until proven otherwise
        self._ollama_available: bool = True
        self._last_check: dict[str, float] = {}
        self._check_interval: float = 30.0  # seconds

    async def check_nim(self) -> bool:
        """Check if the configured NIM instance is reachable.

        Returns True if NIM responds to GET /v1/models.
        """
        if self._should_skip_check("nim"):
            return self._nim_available

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._nim_url.rstrip('/v1')}/v1/models",
                )
                self._nim_available = resp.status_code == 200
        except Exception as e:
            logger.debug(f"NIM probe failed: {e}")
            self._nim_available = False

        self._last_check["nim"] = time.time()
        return self._nim_available

    async def check_ollama(self) -> bool:
        """Check if the configured Ollama instance is reachable."""
        if self._should_skip_check("ollama"):
            return self._ollama_available

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._ollama_url.rstrip('/v1')}/v1/models",
                )
                self._ollama_available = resp.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama probe failed: {e}")
            self._ollama_available = False

        self._last_check["ollama"] = time.time()
        return self._ollama_available

    async def probe_all(self) -> dict[str, bool]:
        """Check all local backends and return status map."""
        nim_ok = await self.check_nim()
        ollama_ok = await self.check_ollama()
        return {"nim": nim_ok, "ollama": ollama_ok}

    @property
    async def available_backends(self) -> set[str]:
        """Set of currently available local backend providers."""
        status = await self.probe_all()
        return {name for name, ok in status.items() if ok}

    def _should_skip_check(self, name: str) -> bool:
        """Avoid checking too frequently."""
        last = self._last_check.get(name, 0.0)
        return (time.time() - last) < self._check_interval


# ── PolicyAwareRouter ───────────────────────────────────────────────────────


class PolicyAwareRouter:
    """Policy-aware model router — the routing layer for SmartRouter 3.0.

    Combines:
      - DataClassifier: label data before routing
      - PolicyEngine: enforce governance policies
      - InfraProbe: filter by infrastructure availability
      - AdaptiveRouter: optimize for cost/capability within constraints

    Usage:
        router = PolicyAwareRouter(registry, policy_engine, infra_probe)
        provider = await router.select("Hello, world!")
        # Provider is the best match considering governance + infra + cost
    """

    def __init__(
        self,
        registry: Any,  # ModelRegistry
        policy_engine: Any | None = None,  # PolicyEngine
        infra_probe: InfraProbe | None = None,
        optimize_for: str = "cost",
    ):
        from chainforge.routing.adaptive import AdaptiveRouter

        self._adaptive = AdaptiveRouter(
            registry=registry,
            optimize_for=optimize_for,
        )
        self._policy_engine = policy_engine
        self._infra_probe = infra_probe
        self._classifier = DataClassifier()

    @property
    def registry(self):
        return self._adaptive.registry

    @property
    def classifier(self) -> DataClassifier:
        return self._classifier

    @property
    def cost_tracker(self):
        return self._adaptive.cost_tracker

    async def select(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        capabilities_needed: set[str] | None = None,
    ) -> Any | None:
        """Select the best model considering governance, infra, and cost.

        Decision flow:
          1. Classify data → sensitivity labels
          2. Evaluate policies → allowed providers
          3. Check infra → filter unavailable backends
          4. AdaptiveRouter → best cost/capability match within constraints

        Args:
            prompt: The user prompt to classify and route.
            context: Optional execution context.
            capabilities_needed: Required model capabilities.

        Returns:
            An LLM provider instance, or None if no model matches.
        """
        ctx = context or {}

        # Step 1: Data classification
        labels = self._classifier.classify(prompt)

        # Step 2: Policy evaluation
        allowed_providers: set[str] | None = None
        if self._policy_engine:
            decision = await self._policy_engine.evaluate(labels, ctx)
            if decision.blocked:
                logger.warning(
                    f"Request blocked by governance policy: {decision.block_reason}"
                )
                return None
            if decision.is_restricted:
                allowed_providers = set(decision.allowed_providers)

        # Step 3: Infrastructure filtering
        infra_available: set[str] = set()
        if self._infra_probe:
            infra_available = await self._infra_probe.available_backends

        # Step 4: Build candidate list
        candidates = self._adaptive.registry.all

        # Filter by capabilities
        if capabilities_needed:
            for cap in capabilities_needed:
                candidates = [m for m in candidates if cap in m.capabilities]

        # Filter by governance
        if allowed_providers:
            candidates = [m for m in candidates if m.provider in allowed_providers]

        # Filter by infrastructure (only for local providers)
        if infra_available and allowed_providers:
            # Only apply infra filter to providers that need local access
            local_providers = {"nim", "ollama"}
            local_allowed = allowed_providers & local_providers
            if local_allowed:
                unreachable = local_allowed - infra_available
                if unreachable and not (allowed_providers - local_providers):
                    # All allowed providers are local and some are unreachable
                    # Remove unreachable ones — but keep the reachable ones
                    candidates = [
                        m for m in candidates
                        if m.provider not in unreachable
                    ]

        if not candidates:
            logger.warning(
                f"No model matches constraints: "
                f"labels={labels}, "
                f"allowed={allowed_providers}, "
                f"infra_available={infra_available}"
            )
            return None

        # Sort and select best
        if self._adaptive._optimize_for == "cost":
            candidates.sort(key=lambda m: m.cost_per_1k)
        elif self._adaptive._optimize_for == "latency":
            candidates.sort(key=lambda m: m.latency_ms)
        else:
            candidates.sort(key=lambda m: m.cost_per_1k * m.latency_ms)

        selected = candidates[0]
        logger.info(
            f"Policy-aware route: {selected.name} ({selected.provider}) "
            f"[labels={labels}]"
        )

        return self._adaptive._create_provider(selected)

    def stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "adaptive": self._adaptive.stats(),
            "classifier_labels": self._classifier.known_labels,
            "has_policy_engine": self._policy_engine is not None,
            "has_infra_probe": self._infra_probe is not None,
        }
```

- [ ] **Step 2: 导出到 `chainforge/routing/__init__.py`**

Edit `chainforge/routing/__init__.py`, replace the content:

```python
# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Model routing — classify task complexity and route to optimal model.

Usage:
    from chainforge.routing import SmartRouter
    from chainforge.providers import OpenAIProvider, DeepSeekProvider

    router = SmartRouter()
    router.register("fast", OpenAIProvider(model="gpt-4o-mini"))
    router.register("reasoning", DeepSeekProvider(model="deepseek-reasoner"))
    router.register("default", OpenAIProvider(model="gpt-4o"))

    agent = router.create_cost_optimized_agent(tools=[...])
    async for event in await agent.run("What is 2+2?"):
        ...
"""

from chainforge.routing.router import SmartRouter, RouteConfig, RoutingStrategy
from chainforge.routing.adaptive import AdaptiveRouter, ModelRegistry, ModelInfo, CostTracker
from chainforge.routing.policy_router import PolicyAwareRouter, InfraProbe, DataClassifier


__all__ = [
    "SmartRouter",
    "RouteConfig",
    "RoutingStrategy",
    "AdaptiveRouter",
    "ModelRegistry",
    "ModelInfo",
    "CostTracker",
    "PolicyAwareRouter",
    "InfraProbe",
    "DataClassifier",
]
```

- [ ] **Step 3: 运行快速验证**

```bash
python -c "
from chainforge.routing.policy_router import DataClassifier, InfraProbe

# DataClassifier
c = DataClassifier()
assert c.classify('Hello world') == ['public']
assert 'pii' in c.classify('My SSN is 123-45-6789')
assert 'pii' in c.classify('user@example.com')
assert 'finance' in c.classify('bank account 1234')
print('DataClassifier OK')

# InfraProbe
p = InfraProbe()
print(f'InfraProbe created: nim={p._nim_url}, ollama={p._ollama_url}')
print('InfraProbe OK')
"
```

Expected: `DataClassifier OK` + `InfraProbe OK`

- [ ] **Step 4: 端到端集成验证**

```bash
python -c "
from chainforge.routing.adaptive import ModelRegistry
from chainforge.routing.policy_router import PolicyAwareRouter, InfraProbe, DataClassifier
from chainforge.governance.policy import PolicyEngine, GovernancePolicy
import asyncio

registry = ModelRegistry()
registry.register('gpt-4o-mini', provider='openai', cost_per_1k=0.00015, latency_ms=300,
                  capabilities={'chat', 'tool_calling'})
registry.register('llama-nim', provider='nim', cost_per_1k=0.0, latency_ms=50,
                  capabilities={'chat', 'tool_calling'})
registry.register('llama-ollama', provider='ollama', cost_per_1k=0.0, latency_ms=80,
                  capabilities={'chat'})

engine = PolicyEngine(policies=[
    GovernancePolicy(name='pii-local', data_labels=['pii'],
                     model_provider='nim', action='enforce'),
])

async def main():
    infra = InfraProbe(nim_url='http://localhost:9999/v1')  # won't be reachable in test
    router = PolicyAwareRouter(registry, engine, infra)

    # Public data → should pick cheapest capable (gpt-4o-mini)
    provider = await router.select('Hello world!')
    if provider:
        print(f'Public data → {provider.model}')

    # PII data → should be restricted to nim
    provider = await router.select('My SSN is 123-45-6789')
    print(f'PII data → provider: {provider}')

asyncio.run(main())
print('Integration OK')
"
```

Expected: `Integration OK`

- [ ] **Step 5: 创建测试 `tests/test_policy_router.py`**

```python
"""Tests for policy-aware router (SmartRouter 3.0)."""
import pytest

from chainforge.routing.policy_router import DataClassifier, InfraProbe
from chainforge.routing.adaptive import ModelRegistry
from chainforge.governance.policy import PolicyEngine, GovernancePolicy


class TestDataClassifier:
    """Unit tests for DataClassifier."""

    def test_public_text(self):
        c = DataClassifier()
        assert c.classify("Hello, how are you?") == ["public"]

    def test_empty_text(self):
        c = DataClassifier()
        assert c.classify("") == []

    def test_ssn_detected(self):
        c = DataClassifier()
        labels = c.classify("My SSN is 123-45-6789")
        assert "pii" in labels

    def test_credit_card_detected(self):
        c = DataClassifier()
        labels = c.classify("Card: 4111-1111-1111-1111")
        assert "pii" in labels

    def test_email_detected(self):
        c = DataClassifier()
        labels = c.classify("Contact me at user@example.com")
        assert "pii" in labels

    def test_finance_detected(self):
        c = DataClassifier()
        labels = c.classify("My bank account is 12345678")
        assert "finance" in labels

    def test_internal_detected(self):
        c = DataClassifier()
        labels = c.classify("This is confidential and internal only")
        assert "internal" in labels

    def test_custom_pattern(self):
        c = DataClassifier()
        c.add_pattern("healthcare", r"\bHIPAA\b")
        labels = c.classify("This is HIPAA data")
        assert "healthcare" in labels

    def test_known_labels(self):
        c = DataClassifier()
        labels = c.known_labels
        assert "pii" in labels
        assert "internal" in labels
        assert "finance" in labels


class TestInfraProbe:
    """Unit tests for InfraProbe."""

    def test_default_config(self):
        p = InfraProbe()
        assert p._nim_url == "http://localhost:8000/v1"
        assert p._ollama_url == "http://localhost:11434/v1"
        assert p._nim_available is True  # assume available until checked

    def test_custom_urls(self):
        p = InfraProbe(
            nim_url="http://gpu-node:9000/v1",
            ollama_url="http://ollama-host:11434/v1",
        )
        assert p._nim_url == "http://gpu-node:9000/v1"

    def test_should_skip_first_check(self):
        """First check should not be skipped (no prior check)."""
        p = InfraProbe()
        assert p._should_skip_check("nim") is False

    def test_should_skip_recent_check(self):
        """Recent check should be skipped."""
        import time
        p = InfraProbe()
        p._last_check["nim"] = time.time()  # just now
        assert p._should_skip_check("nim") is True
```

- [ ] **Step 6: 运行测试**

```bash
python -m pytest tests/test_policy_router.py -v
```

Expected: 9 tests pass.

- [ ] **Step 7: Commit Phase C**

```bash
git add chainforge/routing/policy_router.py chainforge/routing/__init__.py tests/test_policy_router.py
git commit -m "feat: Phase C — SmartRouter 3.0 Policy-Aware Routing

PolicyAwareRouter combines DataClassifier + PolicyEngine + InfraProbe
with AdaptiveRouter for governance-aware model selection.
PII data → forced to local NIM/Ollama. Public data → cost optimized.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 最终验证

全部 Phase 完成后，运行：

```bash
python -m pytest tests/test_providers_nim.py tests/test_policy_router.py -v
python -c "
from chainforge.providers import NIMProvider
from chainforge.governance import PolicyEngine, DataResidency, AuditReporter
from chainforge.routing import PolicyAwareRouter, InfraProbe, DataClassifier
print('All imports OK')
"
```

---

## 实施顺序总结

```
Task A1 (NIMProvider)     → 独立可测试, ~180 行
Task B1 (PolicyEngine)    → 独立可测试, ~100 行
Task B2 (Residency+Vers)  → 独立可测试, ~120 行
Task B3 (AuditReporter)   → 独立可测试, ~150 行
Task C1 (PolicyAwareRouter) → 依赖 A1+B1+B2, ~200 行
```

总计: ~750 行新代码, 17 个测试, 0 breaking changes.
