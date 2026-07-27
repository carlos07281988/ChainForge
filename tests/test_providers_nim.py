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
        with patch.object(NIMProvider, "health_check", new_callable=AsyncMock) as mock_hc:
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
