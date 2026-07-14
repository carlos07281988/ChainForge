# Copyright 2024 ChainForge Contributors
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
"""Agent builder — construct ChainForge Agent instances from AgentConfig."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chainforge.config.schema import AgentConfig, LLMConfig, ToolConfig, MemoryConfig
from chainforge.logging import get_logger, log_data

logger = get_logger("config.builder")

_INFO = 20  # logging.INFO equivalent


def _build_llm(config: LLMConfig) -> Any:
    """Build an LLM provider from config."""
    provider_map = {
        "openai": ("chainforge.providers.openai", "OpenAIProvider"),
        "anthropic": ("chainforge.providers.anthropic", "AnthropicProvider"),
        "google": ("chainforge.providers.google", "GoogleProvider"),
        "azure": ("chainforge.providers.azure", "AzureProvider"),
        "bedrock": ("chainforge.providers.bedrock", "BedrockProvider"),
    }

    if config.provider not in provider_map:
        raise ValueError(f"Unknown provider: {config.provider}. Supported: {list(provider_map.keys())}")

    module_path, class_name = provider_map[config.provider]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    kwargs = {"model": config.model}
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.max_tokens is not None:
        kwargs["max_tokens"] = config.max_tokens
    if config.api_key is not None:
        # Provider-specific API key setting
        pass  # Providers read from env vars by default

    return cls(**kwargs)


def _build_tools(tool_configs: list[ToolConfig]) -> list[Any]:
    """Build tool list from config."""
    tools = []
    for tc in tool_configs:
        if tc.type == "builtin":
            # Load from builtin tools module
            tool = _load_builtin_tool(tc.name)
            if tool:
                tools.append(tool)
        elif tc.type == "skill":
            # Load skill as tool
            from chainforge.skills.loader import load_skill_from_file
            skill = load_skill_from_file(tc.name)
            if skill:
                for t in skill.tools:
                    tools.append(t)
        elif tc.type == "mcp":
            # Dynamic MCP tool loading
            tools.append(_create_mcp_tool_stub(tc))
        elif tc.type == "python":
            # Import a Python function as a tool
            tool = _import_python_tool(tc.name)
            if tool:
                tools.append(tool)
    return tools


def _load_builtin_tool(name: str) -> Any:
    """Load a tool by name from chainforge.tools.builtin."""
    from chainforge.tools import builtin
    return getattr(builtin, name, None)


def _import_python_tool(dotted_path: str) -> Any:
    """Import a tool function from a dotted Python path.

    Example: "my_project.tools.search_web"
    """
    import importlib
    parts = dotted_path.split(".")
    module_path = ".".join(parts[:-1])
    func_name = parts[-1]
    try:
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to import tool '{dotted_path}': {e}")
        return None


def _create_mcp_tool_stub(config: ToolConfig) -> Any:
    """Create a stub for an MCP tool."""
    from chainforge.core.tool import tool
    name = config.name

    @tool
    async def _mcp_tool(**kwargs) -> str:
        return f"[MCP tool '{name}' not connected]"

    _mcp_tool.spec.name = name
    _mcp_tool.spec.description = config.config.get("description", f"MCP tool: {name}")
    return _mcp_tool


def _build_memory(config: MemoryConfig | None) -> Any:
    """Build memory from config."""
    if config is None:
        return None

    if config.type == "buffer":
        from chainforge.memory.buffer import BufferMemory
        max_messages = config.config.get("max_messages", 20)
        return BufferMemory(max_messages=max_messages)

    elif config.type == "summary":
        from chainforge.memory.summary import SummaryMemory
        max_messages = config.config.get("max_messages", 20)
        return SummaryMemory(max_messages=max_messages)

    elif config.type == "vector":
        from chainforge.memory.vector import VectorMemory
        from chainforge.memory.manager import MemoryManager
        from chainforge.memory.buffer import BufferMemory

        memory = MemoryManager(
            working=BufferMemory(max_messages=20),
            episodic=VectorMemory(),
            semantic=VectorMemory() if config.config.get("semantic", True) else None,
        )
        return memory

    return None


def build_agent_from_config(config: AgentConfig) -> Any:
    """Build a ChainForge Agent from an AgentConfig.

    Args:
        config: Parsed agent configuration.

    Returns:
        A configured chainforge Agent instance.

    Usage:
        from chainforge.config.loader import load_agent_config
        from chainforge.config.builder import build_agent_from_config

        config = load_agent_config("agent.yaml")
        agent = build_agent_from_config(config)
        stream = await agent.run("Hello!")
    """
    from chainforge.core.agent import Agent

    # Build components
    llm = _build_llm(config.llm)
    tools = _build_tools(config.tools)
    memory = _build_memory(config.memory)

    # Build system prompt
    system_prompt = config.system_prompt
    if memory and not system_prompt:
        system_prompt = "You are a helpful assistant."

    # Create agent
    agent = Agent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        max_iterations=config.max_iterations,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        parallel_tool_calls=config.parallel_tool_calls,
    )

    # Build system prompt with memory hint
    if memory and config.system_prompt is None:
        agent.system_prompt = "You are a helpful assistant with memory."

    log_data(logger, _INFO, f"Built agent '{config.name}'", data={
        "llm": f"{config.llm.provider}/{config.llm.model}",
        "tools": [t.name for t in config.tools],
        "memory": config.memory.type if config.memory else "none",
    })

    return agent
