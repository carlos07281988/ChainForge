"""Tests for policy-aware router (SmartRouter 3.0)."""
from __future__ import annotations

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
        assert p._nim_available is True

    def test_custom_urls(self):
        p = InfraProbe(
            nim_url="http://gpu-node:9000/v1",
            ollama_url="http://ollama-host:11434/v1",
        )
        assert p._nim_url == "http://gpu-node:9000/v1"

    def test_should_skip_first_check(self):
        p = InfraProbe()
        assert p._should_skip_check("nim") is False

    def test_should_skip_recent_check(self):
        import time
        p = InfraProbe()
        p._last_check["nim"] = time.time()
        assert p._should_skip_check("nim") is True


class TestPolicyAwareRouterIntegration:
    """Integration tests for PolicyAwareRouter."""

    def test_registry_access(self):
        """Router exposes the underlying registry."""
        registry = ModelRegistry()
        registry.register("test-model", provider="nim")
        from chainforge.routing.policy_router import PolicyAwareRouter
        router = PolicyAwareRouter(registry)
        assert router.registry.get("test-model") is not None

    def test_classifier_access(self):
        """Router exposes the DataClassifier."""
        registry = ModelRegistry()
        from chainforge.routing.policy_router import PolicyAwareRouter
        router = PolicyAwareRouter(registry)
        assert isinstance(router.classifier, DataClassifier)

    def test_stats(self):
        """Router stats include relevant keys."""
        registry = ModelRegistry()
        registry.register("test-model", provider="nim")
        engine = PolicyEngine(policies=[
            GovernancePolicy(name="test", data_labels=["pii"],
                           model_provider="nim", action="enforce"),
        ])
        from chainforge.routing.policy_router import PolicyAwareRouter
        router = PolicyAwareRouter(registry, engine)
        s = router.stats()
        assert "classifier_labels" in s
        assert s["has_policy_engine"] is True
        assert s["has_infra_probe"] is False

    @pytest.mark.asyncio
    async def test_select_public_data_routes_to_cheapest(self):
        """Public data should route to the cheapest capable model."""
        registry = ModelRegistry()
        registry.register("gpt-4o-mini", provider="openai", cost_per_1k=0.00015,
                          capabilities={"chat", "tool_calling"})
        registry.register("llama-nim", provider="nim", cost_per_1k=0.0,
                          capabilities={"chat", "tool_calling"})

        from chainforge.routing.policy_router import PolicyAwareRouter
        router = PolicyAwareRouter(registry)

        provider = await router.select("Hello, how are you?")
        assert provider is not None
        # Public data → cheapest: llama-nim (0.0)
        assert provider.model == "llama-nim"

    @pytest.mark.asyncio
    async def test_select_pii_data_restricted_to_nim(self):
        """PII data with nim-enforce policy should only return nim."""
        registry = ModelRegistry()
        registry.register("gpt-4o-mini", provider="openai", cost_per_1k=0.00015,
                          capabilities={"chat", "tool_calling"})
        registry.register("llama-nim", provider="nim", cost_per_1k=0.0,
                          capabilities={"chat", "tool_calling"})

        engine = PolicyEngine(policies=[
            GovernancePolicy(name="pii-local", data_labels=["pii"],
                           model_provider="nim", action="enforce"),
        ])
        from chainforge.routing.policy_router import PolicyAwareRouter
        router = PolicyAwareRouter(registry, engine)

        provider = await router.select("My SSN is 123-45-6789")
        assert provider is not None
        # PII detected → forced to nim
        assert provider.model == "llama-nim"

    @pytest.mark.asyncio
    async def test_select_no_matching_model_returns_none(self):
        """When no model matches constraints, return None."""
        registry = ModelRegistry()
        # Only register models not matching the nim requirement
        registry.register("gpt-4o-mini", provider="openai", cost_per_1k=0.00015,
                          capabilities={"chat"})

        engine = PolicyEngine(policies=[
            GovernancePolicy(name="pii-local", data_labels=["pii"],
                           model_provider="nim", action="enforce"),
        ])
        from chainforge.routing.policy_router import PolicyAwareRouter
        router = PolicyAwareRouter(registry, engine)

        provider = await router.select("My SSN is 123-45-6789")
        assert provider is None
