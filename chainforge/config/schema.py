"""Agent configuration schema — YAML/JSON declarations for ChainForge agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(description="Provider name: openai, anthropic, google, azure, bedrock")
    model: str = Field(default="gpt-4o", description="Model name")
    temperature: float | None = Field(default=None, description="Sampling temperature")
    max_tokens: int | None = Field(default=None, description="Max tokens per response")
    api_key: str | None = Field(default=None, description="API key (supports ${ENV_VAR} syntax)")


class ToolConfig(BaseModel):
    """Tool reference configuration."""

    name: str = Field(description="Tool name")
    type: str = Field(default="builtin", description="Tool source: builtin, mcp, skill, python")
    config: dict[str, Any] = Field(default_factory=dict, description="Tool-specific configuration")


class MemoryConfig(BaseModel):
    """Memory configuration."""

    type: str = Field(default="buffer", description="Memory type: buffer, summary, vector")
    backend: str = Field(default="memory", description="Storage backend: memory, sqlite")
    config: dict[str, Any] = Field(default_factory=dict, description="Memory-specific options")


class MiddlewareConfig(BaseModel):
    """Middleware configuration."""

    name: str = Field(description="Middleware name")
    config: dict[str, Any] = Field(default_factory=dict, description="Middleware options")


class AgentConfig(BaseModel):
    """Complete agent configuration.

    Can be loaded from YAML or JSON:

    ```yaml
    name: research-assistant
    llm:
      provider: openai
      model: gpt-4o
      temperature: 0.3
    tools:
      - name: web_search
        type: builtin
    system_prompt: "You are a research assistant."
    memory:
      type: vector
    ```
    """

    name: str = Field(default="agent", description="Agent name")
    llm: LLMConfig = Field(description="LLM configuration")
    tools: list[ToolConfig] = Field(default_factory=list, description="Tools to load")
    memory: MemoryConfig | None = Field(default=None, description="Memory configuration")
    middlewares: list[MiddlewareConfig] = Field(default_factory=list, description="Middleware chain")
    skills: list[str] = Field(default_factory=list, description="Skill file paths")
    system_prompt: str | None = Field(default=None, description="System prompt")
    max_iterations: int = Field(default=10, description="Max tool-use iterations")
    temperature: float | None = Field(default=None, description="Agent temperature override")
    max_tokens: int | None = Field(default=None, description="Max tokens override")
    parallel_tool_calls: bool = Field(default=True, description="Execute tools in parallel")
