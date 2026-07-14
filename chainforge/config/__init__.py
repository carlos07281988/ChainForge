"""Agent Configuration — declare agents with YAML/JSON.

Allows defining ChainForge agents via declarative configuration files,
supporting environment variable injection and component auto-wiring.

Usage:
    from chainforge.config.loader import load_agent_config
    from chainforge.config.builder import build_agent_from_config

    config = load_agent_config("agent.yaml")
    agent = build_agent_from_config(config)
"""

from chainforge.config.schema import AgentConfig, LLMConfig, ToolConfig, MemoryConfig
from chainforge.config.loader import load_agent_config, load_agent_config_from_dict
from chainforge.config.builder import build_agent_from_config

__all__ = [
    "AgentConfig",
    "LLMConfig",
    "ToolConfig",
    "MemoryConfig",
    "load_agent_config",
    "load_agent_config_from_dict",
    "build_agent_from_config",
]
