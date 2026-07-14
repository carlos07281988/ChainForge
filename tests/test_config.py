"""Tests for the config module."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from chainforge.config.schema import AgentConfig, LLMConfig, ToolConfig, MemoryConfig
from chainforge.config.loader import load_agent_config, load_agent_config_from_dict
from chainforge.config.builder import build_agent_from_config


class TestAgentConfigSchema:
    def test_minimal_config(self):
        config = AgentConfig(
            llm=LLMConfig(provider="openai", model="gpt-4o"),
        )
        assert config.name == "agent"
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.tools == []
        assert config.max_iterations == 10

    def test_full_config(self):
        config = AgentConfig(
            name="research",
            llm=LLMConfig(provider="anthropic", model="claude-3-5-sonnet", temperature=0.3),
            tools=[ToolConfig(name="web_search", type="builtin")],
            memory=MemoryConfig(type="vector", backend="memory"),
            system_prompt="You are a researcher.",
            max_iterations=20,
        )
        assert config.name == "research"
        assert config.llm.temperature == 0.3
        assert len(config.tools) == 1
        assert config.tools[0].name == "web_search"
        assert config.memory is not None
        assert config.memory.type == "vector"

    def test_env_var_default(self):
        # Test that the model can hold env var values
        config = AgentConfig(
            llm=LLMConfig(provider="openai", model="gpt-4o", api_key="${OPENAI_API_KEY}"),
        )
        assert config.llm.api_key == "${OPENAI_API_KEY}"


class TestLoadAgentConfig:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write(self, name: str, content: str) -> str:
        path = Path(self.tmpdir) / name
        path.write_text(content)
        return str(path)

    def test_load_json(self):
        data = {
            "name": "test-agent",
            "llm": {"provider": "openai", "model": "gpt-4o"},
            "tools": [{"name": "calculate", "type": "builtin"}],
        }
        path = self._write("agent.json", json.dumps(data))
        config = load_agent_config(path)
        assert config.name == "test-agent"
        assert config.llm.provider == "openai"
        assert len(config.tools) == 1

    def test_load_from_dict(self):
        data = {
            "name": "dict-agent",
            "llm": {"provider": "anthropic", "model": "claude-3-5-sonnet"},
        }
        config = load_agent_config_from_dict(data)
        assert config.name == "dict-agent"
        assert config.llm.model == "claude-3-5-sonnet"

    def test_env_var_injection(self):
        os.environ["_TEST_API_KEY"] = "sk-test123"
        data = {
            "name": "env-agent",
            "llm": {"provider": "openai", "model": "gpt-4o", "api_key": "${_TEST_API_KEY}"},
        }
        config = load_agent_config_from_dict(data)
        assert config.llm.api_key == "sk-test123"
        del os.environ["_TEST_API_KEY"]

    def test_env_var_with_default(self):
        data = {
            "name": "default-agent",
            "llm": {"provider": "openai", "model": "gpt-4o", "api_key": "${MISSING_VAR:-default-key}"},
        }
        config = load_agent_config_from_dict(data)
        assert config.llm.api_key == "default-key"

    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_agent_config("/nonexistent/config.yaml")

    def test_unsupported_format(self):
        path = self._write("config.toml", "[agent]\nname = 'test'")
        with pytest.raises(ValueError, match="Unsupported config format"):
            load_agent_config(path)


class TestBuildAgentFromConfig:
    def test_build_minimal(self):
        config = AgentConfig(
            llm=LLMConfig(provider="openai", model="gpt-4o"),
        )
        agent = build_agent_from_config(config)
        assert agent is not None
        assert agent.max_iterations == 10

    def test_build_with_tools(self):
        config = AgentConfig(
            llm=LLMConfig(provider="openai", model="gpt-4o"),
            tools=[ToolConfig(name="calculate", type="builtin")],
        )
        agent = build_agent_from_config(config)
        assert agent is not None
        tools = agent._all_tools()
        assert len(tools) >= 1

    def test_build_with_memory_config(self):
        config = AgentConfig(
            llm=LLMConfig(provider="openai", model="gpt-4o"),
            memory=MemoryConfig(type="buffer", config={"max_messages": 10}),
        )
        agent = build_agent_from_config(config)
        assert agent is not None

    def test_build_unknown_provider(self):
        config = AgentConfig(
            llm=LLMConfig(provider="nonexistent", model="x"),
        )
        with pytest.raises(ValueError):
            build_agent_from_config(config)
