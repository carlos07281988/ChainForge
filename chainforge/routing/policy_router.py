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

from chainforge.logging import get_logger

logger = get_logger("routing.policy_router")


# ── DataClassifier ──────────────────────────────────────────────────────────


_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("pii", re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
        r"|\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
        r"|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        r"|\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b"
        r"|\b(?:passport|身份证|护照)\s*[#:：]?\s*\w+\b"
        r"|\b(?:password|密码|secret|token)\s*[=:：]\s*\S+\b",
        re.IGNORECASE,
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
        self._nim_available: bool = True
        self._ollama_available: bool = True
        self._last_check: dict[str, float] = {}
        self._check_interval: float = 30.0

    async def check_nim(self) -> bool:
        """Check if the configured NIM instance is reachable."""
        if self._should_skip_check("nim"):
            return self._nim_available

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._nim_url.removesuffix('/v1')}/v1/models",
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
                    f"{self._ollama_url.removesuffix('/v1')}/v1/models",
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

        # Step 3: Infrastructure filtering (only when policies constrain providers)
        infra_available: set[str] = set()
        if self._infra_probe and allowed_providers:
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

        # Filter by infrastructure (local providers)
        if infra_available and allowed_providers:
            local_providers = {"nim", "ollama"}
            local_allowed = allowed_providers & local_providers
            if local_allowed:
                unreachable = local_allowed - infra_available
                if unreachable and not (allowed_providers - local_providers):
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

        # Sort by optimization goal
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
