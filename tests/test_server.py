"""Tests for HTTP server and client."""

import pytest
from chainforge.server import register_agent, app, _agent_registry
from chainforge.client import ChainForgeClient


class FakeLLM:
    model = "fake"
    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        return LLMResponse(content="test response")
    async def stream_generate(self, messages, tools=None, **kwargs):
        yield "test"


class TestServerRegistry:
    def setup_method(self):
        _agent_registry.clear()

    def test_register_agent(self):
        from chainforge.core.agent import Agent
        _agent_registry.clear()
        register_agent("test", Agent(llm=FakeLLM()), "Test agent")
        assert "test" in _agent_registry

    def test_get_agent_info(self):
        from chainforge.core.agent import Agent
        _agent_registry.clear()
        register_agent("info_test", Agent(llm=FakeLLM()), "Info agent")
        agent, entry = _agent_registry["info_test"], _agent_registry["info_test"]
        assert entry["description"] == "Info agent"


class TestClient:
    def test_client_creation(self):
        client = ChainForgeClient("http://localhost:8000")
        assert client.base_url == "http://localhost:8000"

    def test_client_custom_timeout(self):
        client = ChainForgeClient("http://localhost:8000", timeout=300)
        assert client.timeout == 300

    def test_client_api_key(self):
        client = ChainForgeClient("http://localhost:8000", api_key="sk-secret")
        assert "Bearer sk-secret" in str(client._headers())


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        from fastapi.testclient import TestClient
        _agent_registry.clear()
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestRunEndpoint:
    @pytest.mark.asyncio
    async def test_run_agent(self):
        from fastapi.testclient import TestClient
        from chainforge.core.agent import Agent
        _agent_registry.clear()
        register_agent("test_agent", Agent(llm=FakeLLM()), "Test")

        test_client = TestClient(app)
        resp = test_client.post("/api/v1/agents/test_agent/run", json={"prompt": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "output" in data
        assert "duration_s" in data

    @pytest.mark.asyncio
    async def test_run_missing_agent(self):
        from fastapi.testclient import TestClient
        _agent_registry.clear()
        test_client = TestClient(app)
        resp = test_client.post("/api/v1/agents/nonexistent/run", json={"prompt": "Hello"})
        assert resp.status_code == 404


class TestStreamEndpoint:
    @pytest.mark.asyncio
    async def test_stream_agent(self):
        from fastapi.testclient import TestClient
        from chainforge.core.agent import Agent
        _agent_registry.clear()
        register_agent("stream_agent", Agent(llm=FakeLLM()), "Stream test")

        test_client = TestClient(app)
        resp = test_client.get("/api/v1/agents/stream_agent/run/stream", params={"prompt": "Hello"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_agent_info(self):
        from fastapi.testclient import TestClient
        from chainforge.core.agent import Agent
        _agent_registry.clear()
        register_agent("info_agent", Agent(llm=FakeLLM()), "Info")
        test_client = TestClient(app)
        resp = test_client.get("/api/v1/agents/info_agent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "info_agent"


class TestAgentResult:
    def test_agent_result(self):
        from chainforge.client import AgentResult
        r = AgentResult(output="hello", duration_s=1.5, tool_calls=2, events=[])
        assert r.output == "hello"
        assert r.duration_s == 1.5
        assert r.tool_calls == 2
